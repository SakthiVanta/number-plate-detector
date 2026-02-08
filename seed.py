import logging
from app.db.session import SessionLocal, engine, Base
from app.models.models import User
from app.core.security import get_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_db():
    try:
        # Create tables (idempotent)
        Base.metadata.create_all(bind=engine)
        
        db = SessionLocal()
        
        # Check for admin user
        admin_email = "admin@alpr.pro"
        existing_user = db.query(User).filter(User.email == admin_email).first()
        
        if not existing_user:
            logger.info(f"Creating default admin user: {admin_email}")
            user = User(
                email=admin_email,
                hashed_password=get_password_hash("admin123"),
                full_name="System Administrator",
                role="admin",
                is_active=True
            )
            db.add(user)
            db.commit()
            logger.info("Admin user created successfully.")
        else:
            logger.warning(f"User {admin_email} exists. RESETTING PASSWORD to 'admin123'...")
            existing_user.hashed_password = get_password_hash("admin123")
            db.commit()
            logger.info("Password reset successfully.")

        logger.info("Email: admin@alpr.pro")
        logger.info("Password: admin123")
            
        db.close()
        logger.info("Seeding complete.")
        
    except Exception as e:
        logger.error(f"Seeding failed: {e}")

if __name__ == "__main__":
    seed_db()
