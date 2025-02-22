from werkzeug.security import generate_password_hash, check_password_hash

plaintext = "adminpassword"
hashed = generate_password_hash(plaintext)
print("Hash:", hashed)
print("Check:", check_password_hash(hashed, plaintext))  # Should print True
