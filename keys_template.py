import thalex

# You have to create api keys on thalex ui.
# TEST: https://testnet.thalex.com/exchange/user/api
# PROD: https://thalex.com/exchange/user/api
# If you don't want to quote on test/prod you can just leave the
# corresponding key / key_id as it is.

# Copy this file to keys.py and fill in your actual API keys
private_keys = {
    thalex.Network.TEST: """-----BEGIN RSA PRIVATE KEY-----
YOUR_TEST_PRIVATE_KEY_HERE
-----END RSA PRIVATE KEY-----
""",
    thalex.Network.PROD: """-----BEGIN RSA PRIVATE KEY-----
YOUR_PROD_PRIVATE_KEY_HERE
-----END RSA PRIVATE KEY-----
""",
}

key_ids = {
    thalex.Network.TEST: "YOUR_TEST_KEY_ID",
    thalex.Network.PROD: "YOUR_PROD_KEY_ID",
} 