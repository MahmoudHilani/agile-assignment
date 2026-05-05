import sys
import bcrypt

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/setup_admin.py <password>")
        sys.exit(1)
    hashed = bcrypt.hashpw(sys.argv[1].encode(), bcrypt.gensalt()).decode()
    print(hashed)
