"""Tests for the Secret Santa app.

Runs against an in-memory database with Flask's test client, so no server is
needed and santa.db is not touched:

    python verify.py
"""
import io
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from urllib.parse import urlparse

# Must be set before the app is imported (values from .env don't override these).
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['ADMIN_PIN'] = 'test-pin'
os.environ['SECRET_KEY'] = 'test-secret'

from app import app, db  # noqa: E402


def fake_image(name):
    return (io.BytesIO(b'not really an image'), name)


class SecretSantaTests(unittest.TestCase):
    def setUp(self):
        self.upload_dir = tempfile.mkdtemp()
        app.config.update(
            TESTING=True,
            UPLOAD_FOLDER=self.upload_dir,
            PUBLIC_URL='',
            GIFT_BUDGET='25-30 euro',
            DEADLINE=datetime.now() + timedelta(days=1),
        )
        with app.app_context():
            db.drop_all()
            db.create_all()

        self.admin = app.test_client()
        response = self.admin.post('/api/admin/login', json={'pin': 'test-pin'})
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        shutil.rmtree(self.upload_dir, ignore_errors=True)

    # ------------------------------------------------------------ helpers

    def add(self, name, wishes=(), image=None):
        data = {'name': name, 'wishes': list(wishes)}
        if image:
            data['image'] = image
        response = self.admin.post('/api/admin/participants', data=data)
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def join(self, participant):
        """Open the participant's personal link in a fresh browser."""
        client = app.test_client()
        response = client.get(urlparse(participant['link']).path)
        self.assertEqual(response.status_code, 302)
        return client

    def admin_list(self):
        response = self.admin.get('/api/admin/participants')
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def take(self, client, participant):
        return client.post(f"/api/take/{participant['id']}")

    # -------------------------------------------------------------- tests

    def test_visitor_without_link_is_kept_out(self):
        client = app.test_client()
        page = client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'personal link', page.data)
        self.assertEqual(client.get('/api/me').status_code, 401)
        self.assertEqual(client.get('/api/participants').status_code, 401)
        self.assertEqual(client.post('/api/take/1').status_code, 401)
        self.assertEqual(client.post('/api/me/wishes', json={'wishes': []}).status_code, 401)

    def test_invalid_link(self):
        response = app.test_client().get('/join/not-a-real-token')
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"doesn't work", response.data)

    def test_admin_requires_pin(self):
        client = app.test_client()
        self.assertEqual(client.get('/api/admin/participants').status_code, 401)
        self.assertEqual(client.post('/api/admin/participants', data={'name': 'X'}).status_code, 401)
        self.assertEqual(client.post('/api/admin/login', json={'pin': 'wrong'}).status_code, 401)
        self.assertEqual(client.post('/api/admin/login', json={'pin': 'test-pin'}).status_code, 200)
        self.assertEqual(client.get('/api/admin/participants').status_code, 200)
        client.post('/api/admin/logout')
        self.assertEqual(client.get('/api/admin/participants').status_code, 401)

    def test_admin_input_validation(self):
        def post(data):
            return self.admin.post('/api/admin/participants', data=data).status_code

        self.assertEqual(post({'name': '   '}), 400)
        self.assertEqual(post({'name': 'x' * 101}), 400)
        self.assertEqual(post({'name': 'Anna', 'wishes': ['x' * 501]}), 400)
        self.assertEqual(post({'name': 'Anna', 'wishes': ['a', 'b', 'c', 'd']}), 400)
        self.assertEqual(post({'name': 'Anna', 'image': fake_image('evil.html')}), 400)
        self.assertEqual(self.admin_list()['participants'], [])

    def test_join_signs_in_and_shows_other_participants(self):
        anna = self.add('Anna', ['Socks'])
        bob = self.add('Bob', ['Book', '', 'Tea'])
        self.assertNotEqual(anna['link'], bob['link'])

        client = self.join(anna)
        page = client.get('/').data
        self.assertIn(b'Anna', page)
        self.assertIn(b'Gift budget: <strong>25-30 euro</strong>', page)

        me = client.get('/api/me').get_json()
        self.assertEqual(me['name'], 'Anna')
        self.assertEqual(me['wishes'], ['Socks', '', ''])
        self.assertIsNone(me['gives_to'])

        others = client.get('/api/participants').get_json()
        self.assertEqual([p['name'] for p in others], ['Bob'])
        self.assertNotIn('wishes', others[0])  # hidden until picked
        self.assertNotIn('link', others[0])

        joined = {p['name']: p['joined'] for p in self.admin_list()['participants']}
        self.assertEqual(joined, {'Anna': True, 'Bob': False})

    def test_wishlist_editing(self):
        client = self.join(self.add('Anna'))

        response = client.post('/api/me/wishes', json={'wishes': ['  Socks  ', 'A <b>book</b>\n  ']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['wishes'], ['Socks', 'A <b>book</b>', ''])

        self.assertEqual(client.post('/api/me/wishes', json={'wishes': ['x' * 501]}).status_code, 400)
        self.assertEqual(client.post('/api/me/wishes', json={'wishes': ['a', 'b', 'c', 'd']}).status_code, 400)
        self.assertEqual(client.post('/api/me/wishes', json={'wishes': 'Socks'}).status_code, 400)
        self.assertEqual(client.post('/api/me/wishes', json={'wishes': [1, 2]}).status_code, 400)

        page = client.get('/').data
        self.assertIn(b'>Socks</textarea>', page)
        # Wishes are escaped when put into the page.
        self.assertIn(b'A &lt;b&gt;book&lt;/b&gt;', page)

    def test_picking_rules(self):
        anna, bob, cara = self.add('Anna'), self.add('Bob'), self.add('Cara')
        anna_client, cara_client = self.join(anna), self.join(cara)

        self.assertEqual(self.take(anna_client, anna).status_code, 400)  # yourself
        self.assertEqual(self.take(anna_client, bob).status_code, 200)
        self.assertEqual(self.take(anna_client, bob).get_json()['message'], 'You already picked this person.')
        self.assertEqual(self.take(anna_client, cara).status_code, 400)  # second pick
        self.assertEqual(anna_client.get('/api/me').get_json()['gives_to']['name'], 'Bob')

        bob_for_cara = next(p for p in cara_client.get('/api/participants').get_json() if p['name'] == 'Bob')
        self.assertTrue(bob_for_cara['is_taken'])
        self.assertFalse(bob_for_cara['taken_by_me'])
        self.assertEqual(self.take(cara_client, bob).status_code, 400)  # already taken

        self.assertEqual(anna_client.post('/api/untake').status_code, 200)
        self.assertEqual(anna_client.post('/api/untake').status_code, 400)  # nothing to untake
        self.assertEqual(self.take(cara_client, bob).status_code, 200)
        self.assertEqual(self.take(anna_client, bob).status_code, 400)
        self.assertEqual(self.take(anna_client, {'id': 9999}).status_code, 404)

    def test_wishes_shown_only_after_pick(self):
        anna = self.add('Anna')
        bob = self.add('Bob', ['Book'])
        cara = self.add('Cara', ['Tea'])
        client = self.join(anna)

        def wishes_by_name():
            return {p['name']: p.get('wishes') for p in client.get('/api/participants').get_json()}

        self.assertEqual(wishes_by_name(), {'Bob': None, 'Cara': None})
        self.take(client, bob)
        self.assertEqual(wishes_by_name(), {'Bob': ['Book'], 'Cara': None})
        self.assertEqual(client.get('/api/me').get_json()['gives_to']['wishes'], ['Book'])

    def test_admin_cannot_see_who_picked_whom(self):
        anna, bob = self.add('Anna'), self.add('Bob')
        self.take(self.join(anna), bob)

        data = self.admin_list()
        self.assertEqual(data['picked_count'], 1)
        for participant in data['participants']:
            self.assertEqual(set(participant), {'id', 'name', 'image_url', 'wishes', 'link', 'joined'})

    def test_deadline_locks_picks_and_wishlists(self):
        anna, bob, cara = self.add('Anna'), self.add('Bob'), self.add('Cara')
        client = self.join(anna)
        self.assertEqual(self.take(client, bob).status_code, 200)

        app.config['DEADLINE'] = datetime.now() - timedelta(minutes=1)
        self.assertEqual(client.post('/api/untake').status_code, 403)
        self.assertEqual(self.take(self.join(cara), bob).status_code, 403)
        self.assertEqual(client.post('/api/me/wishes', json={'wishes': ['Late']}).status_code, 403)
        self.assertTrue(client.get('/api/me').get_json()['deadline_passed'])

        page = client.get('/').data
        self.assertIn(b'disabled', page)
        self.assertNotIn(b'Save wishlist', page)

        # The organizer can still fix things after the deadline.
        response = self.admin.post(f"/api/admin/participants/{anna['id']}", data={'name': 'Anna', 'wishes': ['Fixed']})
        self.assertEqual(response.status_code, 200)

    def test_new_link_signs_out_old_browsers(self):
        anna = self.add('Anna')
        old_client = self.join(anna)
        self.assertEqual(self.take(old_client, self.add('Bob')).status_code, 200)

        renewed = self.admin.post(f"/api/admin/participants/{anna['id']}/regenerate").get_json()
        self.assertNotEqual(renewed['link'], anna['link'])
        self.assertFalse(renewed['joined'])

        self.assertEqual(old_client.get('/api/me').status_code, 401)
        self.assertIn(b'personal link', old_client.get('/').data)
        self.assertEqual(app.test_client().get(urlparse(anna['link']).path).status_code, 404)

        new_client = self.join(renewed)
        me = new_client.get('/api/me').get_json()
        self.assertEqual(me['gives_to']['name'], 'Bob')  # the pick survives

    def test_edit_participant_replaces_image(self):
        bob = self.add('Bob', image=fake_image('bob.png'))
        self.assertTrue(bob['image_url'].startswith('/static/uploads/'))
        self.assertEqual(len(os.listdir(self.upload_dir)), 1)

        response = self.admin.post(
            f"/api/admin/participants/{bob['id']}",
            data={'name': 'Bobby', 'wishes': ['Tea', '', ''], 'image': fake_image('new.jpg')},
        )
        self.assertEqual(response.status_code, 200)
        updated = response.get_json()
        self.assertEqual(updated['name'], 'Bobby')
        self.assertEqual(updated['wishes'], ['Tea', '', ''])
        self.assertEqual(os.listdir(self.upload_dir), [updated['image_url'].rsplit('/', 1)[1]])

    def test_delete_participant_frees_pick_and_removes_image(self):
        anna = self.add('Anna')
        bob = self.add('Bob', image=fake_image('bob.png'))
        anna_client = self.join(anna)
        bob_client = self.join(bob)
        self.take(anna_client, bob)

        self.assertEqual(self.admin.delete(f"/api/admin/participants/{bob['id']}").status_code, 200)
        self.assertIsNone(anna_client.get('/api/me').get_json()['gives_to'])
        self.assertEqual(os.listdir(self.upload_dir), [])
        self.assertEqual(bob_client.get('/api/me').status_code, 401)

    def test_logout(self):
        client = self.join(self.add('Anna'))
        self.assertEqual(client.post('/logout').status_code, 302)
        self.assertEqual(client.get('/api/me').status_code, 401)


if __name__ == '__main__':
    unittest.main(verbosity=2)
