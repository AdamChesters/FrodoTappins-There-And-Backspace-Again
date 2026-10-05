"""Public feedback transport. No counts, configuration or logs are attached."""
import json
import re
import urllib.request

from .content import CONTENT

FEEDBACK_URL = CONTENT['feedback']['endpoint']

def payload(name, email, message, appId, appVersion):
    fields = dict(name=name.strip(), email=email.strip(), message=message.strip())
    if not fields['name'] or len(fields['name']) > 100:
        raise ValueError('Enter your name (up to 100 characters).')
    if len(fields['email']) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', fields['email']):
        raise ValueError('Enter a valid email address.')
    if not fields['message'] or len(fields['message']) > 4000:
        raise ValueError('Enter a message (up to 4000 characters).')
    return dict(app=appId, version=appVersion, **fields)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send(data):
    if not FEEDBACK_URL.startswith('https://'):
        raise ValueError('Feedback delivery is not configured yet.')
    req = urllib.request.Request(FEEDBACK_URL, data=json.dumps(data).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.build_opener(_NoRedirect).open(req, timeout=15) as response:
        raw = response.read(CONTENT['feedback']['ack']['maxBytes'] + 1)
        if len(raw) > CONTENT['feedback']['ack']['maxBytes'] or response.headers.get_content_type() != CONTENT['feedback']['ack']['contentType']:
            raise ValueError('Feedback delivery returned an invalid response.')
        result = json.loads(raw)
        if response.status != 200 or result != {'ok': True} or type(result.get('ok')) is not bool:
            raise ValueError('Feedback was not accepted. Please try again.')
