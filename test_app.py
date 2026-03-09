from app import create_app
from app.extensions import db
from app.models import User, Product

app = create_app()
app.testing = True

with app.app_context():
    client = app.test_client()

    print('GET /')
    r = client.get('/')
    print(' / ->', r.status_code)

    print('GET /marketplace (no login)')
    r = client.get('/marketplace')
    print(' /marketplace ->', r.status_code)

    # Login using seeded buyer
    email = 'suresh.buyer@construction.com'
    password = 'password123'
    print('GET /login (fetch CSRF)')
    r_get = client.get('/login')
    csrf_token = None
    import re
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', r_get.get_data(as_text=True))
    if m:
        csrf_token = m.group(1)

    print('POST /login')
    post_data = {'email': email, 'password': password}
    if csrf_token:
        post_data['csrf_token'] = csrf_token
    r = client.post('/login', data=post_data, follow_redirects=True)
    print(' login ->', r.status_code)
    if b'Dashboard' in r.data or r.status_code==200:
        print(' Login appears successful')
    else:
        print(' Login may have failed')

    print('GET /dashboard (after login)')
    r = client.get('/dashboard')
    print(' /dashboard ->', r.status_code)

    # Check a product exists
    prod = Product.query.first()
    if prod:
        print('Found product id', prod.id, prod.title)
        # check product detail
        r = client.get(f'/product/{prod.id}')
        print(f'/product/{prod.id} ->', r.status_code)
    else:
        print('No product found')

    # Logout
    print('GET /logout')
    r = client.get('/logout', follow_redirects=True)
    print(' logout ->', r.status_code)
    print('Finished tests')
