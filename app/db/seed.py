from sqlalchemy.orm import Session
from app.db.session import SessionLocal, engine
from app.models.models import User, Base
from app.core.security import get_password_hash

def seed_db():
    print(">>> Refreshing Database Schema...")
    # Drop and Recreate for schema updates
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Check if admin exists
        admin_email = "admin@alpr.pro"
        admin = db.query(User).filter(User.email == admin_email).first()
        
        if not admin:
            print(f"Creating default admin: {admin_email}")
            # Ensure we use a compatible hash
            password = "admin123"
            hashed_pw = get_password_hash(password)
            
            new_admin = User(
                email=admin_email,
                full_name="System Administrator",
                hashed_password=hashed_pw,
                is_active=1 # Integer in model
            )
            db.add(new_admin)
            db.commit()
            print(f"Admin user seeded successfully! Password: {password}")
        else:
            print("Admin user already exists.")
            
    except Exception as e:
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
