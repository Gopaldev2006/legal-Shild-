from sqlalchemy.orm import Session
from app.models.user import User, UserRole, VerificationStatus
from app.core.security import get_password_hash


def init_db(db: Session) -> None:
    """
    Seeds initial controlled demonstration accounts for major project evaluation.
    1. Public User: public@example.com / public123
    2. Unverified Pro: unverified@example.com / unverified123
    3. Verified Legal Pro: advocate@example.com / advocate123
    4. System Admin: admin@example.com / admin123
    """
    demo_users = [
        {
            "name": "John Citizen (Public)",
            "email": "public@example.com",
            "password": "public123",
            "role": UserRole.PUBLIC_USER,
            "status": VerificationStatus.NOT_REQUIRED
        },
        {
            "name": "Adv. Rahul Verma (Unverified)",
            "email": "unverified@example.com",
            "password": "unverified123",
            "role": UserRole.LEGAL_PROFESSIONAL,
            "status": VerificationStatus.PENDING
        },
        {
            "name": "Adv. Priya Sharma (Verified)",
            "email": "advocate@example.com",
            "password": "advocate123",
            "role": UserRole.LEGAL_PROFESSIONAL,
            "status": VerificationStatus.VERIFIED
        },
        {
            "name": "System Administrator",
            "email": "admin@example.com",
            "password": "admin123",
            "role": UserRole.ADMIN,
            "status": VerificationStatus.VERIFIED
        }
    ]

    for data in demo_users:
        existing = db.query(User).filter(User.email == data["email"]).first()
        if not existing:
            user = User(
                name=data["name"],
                email=data["email"],
                password_hash=get_password_hash(data["password"]),
                role=data["role"],
                verification_status=data["status"]
            )
            db.add(user)
    db.commit()
