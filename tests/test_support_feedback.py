import unittest
from unittest.mock import patch, MagicMock
import json
import urllib.error
from donate import support_feedback as feedback


class FeedbackTests(unittest.TestCase):
    def test_payload_identifies_app_and_version_without_private_data(self):
        body = feedback.payload(' Adam ', 'adam@example.test ', ' An idea ', 'FrodoTappins-There-And-Backspace-Again', '0.3.0')
        self.assertEqual(body['app'], 'FrodoTappins-There-And-Backspace-Again')
        self.assertEqual(body['name'], 'Adam')
        self.assertEqual(set(body), {'app', 'version', 'name', 'email', 'message'})
        self.assertEqual(body['version'], '0.3.0')

    def test_invalid_and_oversized_fields_rejected(self):
        for name, email, message in [('', 'a@b.test', 'idea'), ('a' * 101, 'a@b.test', 'idea'),
                                     ('Adam', 'invalid', 'idea'), ('Adam', 'a@b.test', ' '),
                                     ('Adam', 'a@b.test', 'a' * 4001)]:
            with self.assertRaises(ValueError):
                feedback.payload(name, email, message, "FrodoTappins-There-And-Backspace-Again", "0.3.0")

    def test_only_explicit_relay_acceptance_is_success(self):
        response = MagicMock(); response.status = 200
        response.__enter__.return_value = response
        response.headers.get_content_type.return_value = "application/json"
        opener = MagicMock(); opener.open.return_value = response
        data = feedback.payload('Adam', 'a@b.test', 'Idea', 'FrodoTappins-There-And-Backspace-Again', '0.3.0')
        with patch.object(feedback, 'FEEDBACK_URL', 'https://relay.example.test/feedback'), patch.object(feedback.urllib.request, 'build_opener', return_value=opener):
            response.read.return_value = b'{"ok":true}'
            feedback.send(data)
            request = opener.open.call_args.args[0]
            self.assertEqual(json.loads(request.data), data)
            for raw in [b'{"ok":false}', b'{"ok":true,"extra":1}', b'{"ok":1}', b'{"ok":true}' + b' ' * 1024]:
                response.read.return_value = raw
                with self.assertRaises(ValueError):
                    feedback.send(data)

    def test_redirect_does_not_forward_personal_fields(self):
        self.assertIsNone(feedback._NoRedirect().redirect_request(None, None, 307, '', {}, 'https://other.test'))

    def test_unconfigured_endpoint_is_rejected(self):
        with patch.object(feedback, 'FEEDBACK_URL', ''):
            with self.assertRaises(ValueError):
                feedback.send({})
