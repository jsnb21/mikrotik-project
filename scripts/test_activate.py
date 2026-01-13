import urllib.request
import urllib.parse

URL = 'http://127.0.0.1:5000/activate'
DATA = {
    'voucher_code': '5GSD637C',
    'mac_address': '0A:6A:E3:9F:37:2F'
}

data = urllib.parse.urlencode(DATA).encode()
req = urllib.request.Request(URL, data=data, method='POST')
try:
    with urllib.request.urlopen(req, timeout=10) as res:
        print('Final URL:', res.geturl())
        print('Status code:', res.status)
        print('Headers:')
        for h in res.getheaders():
            print('  ', h)
        body = res.read(2000).decode('utf-8', errors='replace')
        print('\nResponse snippet (first 2000 chars):\n')
        print(body)
except Exception as e:
    print('Request error:', e)
