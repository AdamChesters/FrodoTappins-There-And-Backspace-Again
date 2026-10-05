"""Public feedback transport. No counts, configuration or logs are attached."""
import json
import re
import urllib.request

import updater

APP_ID = 'FrodoTappins-There-And-Backspace-Again'
FEEDBACK_URL = 'https://adamch-app-feedback.adam-chesters.workers.dev/feedback'
PAYPAL_URL = "https://www.paypal.com/donate/?business=KLHSZPXTSVSAU&no_recurring=0&item_name=I%27ve+donated+to+lots+of+small+creators+for+their+useful+little+tools%2C+now+I+create+them.+Dig+one?+I%27d+love+your+support.&currency_code=AUD"


def payload(name, email, message):
    fields = dict(name=name.strip(), email=email.strip(), message=message.strip())
    if not fields['name'] or len(fields['name']) > 100:
        raise ValueError('Enter your name (up to 100 characters).')
    if len(fields['email']) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', fields['email']):
        raise ValueError('Enter a valid email address.')
    if not fields['message'] or len(fields['message']) > 4000:
        raise ValueError('Enter a message (up to 4000 characters).')
    return dict(app=APP_ID, version=updater.VERSION, **fields)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send(data):
    if not FEEDBACK_URL.startswith('https://'):
        raise ValueError('Feedback delivery is not configured yet.')
    req = urllib.request.Request(FEEDBACK_URL, data=json.dumps(data).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.build_opener(_NoRedirect).open(req, timeout=15) as response:
        result = json.loads(response.read(8193))
        if response.status != 200 or not isinstance(result, dict) or result.get('ok') is not True:
            raise ValueError('Feedback was not accepted. Please try again.')
