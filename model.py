from sqlalchemy import Column, Integer, ForeignKey, text, String, Boolean, DateTime, Float
from database import Base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key = True, index = True)
    username = Column(String(50), unique = True, index = True, nullable = False)
    email = Column(String(100), unique = True, index = True, nullable = False)
    password_hash = Column(String(128), nullable = False)
    phone = Column(String(15), nullable = True)
    created_at = Column(DateTime(timezone = True), server_default = func.now())
    role = Column(String(20), default="user")
    is_active = Column(Boolean, default = True)
    # Relationships
    vehicles = relationship("Vehicle", back_populates = "owner")
    bookings = relationship("Booking", back_populates = "user")
    parking_sessions = relationship("ParkingSession", back_populates = "user")
    wallet = relationship("Wallet", back_populates="user", uselist=False)

class Vehicle(Base):
    __tablename__ = 'vehicles'

    id = Column(Integer, primary_key = True, index = True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable = False)
    vehicle_number = Column(String(20), unique = True, index=True, nullable = False)
    vehicle_type = Column(String(20), nullable = False)
    created_at = Column(DateTime(timezone = True), server_default = func.now())
    
    # Relationships
    owner = relationship("User", back_populates="vehicles")
    bookings = relationship("Booking", back_populates="vehicle")
    parking_sessions = relationship("ParkingSession", back_populates="vehicle")

class ParkingSlot(Base):
    __tablename__ = 'parking_slots'

    id = Column(Integer, primary_key = True, index = True)
    slot_number = Column(String(10), unique = True, nullable = False)
    vehicle_type = Column(String(20), nullable = False)  # what type of vehicle can park here
    is_occupied = Column(Boolean, default = False)
    is_active = Column(Boolean, default = True)  # for maintenance or deactivation
    zone = Column(String(10), nullable = True)  # e.g., A, B, C zones
    
    # Relationships
    current_session = relationship("ParkingSession", uselist = False, back_populates = "slot")

class Booking(Base):
    __tablename__ = 'bookings'

    id = Column(Integer, primary_key = True, index = True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable = False)
    vehicle_id = Column(Integer, ForeignKey('vehicles.id'), nullable = False)
    booking_time = Column(DateTime(timezone = True), server_default = func.now())
    expected_entry_time = Column(DateTime(timezone = True), nullable = False)
    expected_exit_time = Column(DateTime(timezone = True), nullable = True)
    qr_image_path = Column(String(512), nullable=True)  # Path to generated QR image
    is_active = Column(Boolean, default = True)  # Whether booking is still valid
    is_used = Column(Boolean, default = False)  # Whether booking has been used for entry
    
    # Relationships
    user = relationship("User", back_populates="bookings")
    vehicle = relationship("Vehicle", back_populates="bookings")
    sessions = relationship(
        "ParkingSession",
        back_populates="booking",
        cascade="all, delete-orphan"
    )

class ParkingSession(Base):
    __tablename__ = 'parking_sessions'

    id = Column(Integer, primary_key = True, index = True)
    booking_id = Column(Integer, ForeignKey('bookings.id'), nullable = False, unique = True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable = False)
    vehicle_id = Column(Integer, ForeignKey('vehicles.id'), nullable = False)
    slot_id = Column(Integer, ForeignKey('parking_slots.id'), nullable = True)  # Assigned at entry
    
    entry_time = Column(DateTime(timezone = True), nullable = False)
    exit_time = Column(DateTime(timezone = True), nullable = True)
    
    # Status tracking
    status = Column(String(20), default="active")  # active, completed
    
    # Payment related
    total_fee = Column(Float, nullable = True)
    payment_status = Column(String(20), default = "pending")  # pending, paid
    
    # Relationships
    booking = relationship("Booking", back_populates="sessions")
    user = relationship("User", back_populates = "parking_sessions")
    vehicle = relationship("Vehicle", back_populates = "parking_sessions")
    slot = relationship("ParkingSlot", back_populates = "current_session")
    payment = relationship("Payment", back_populates = "parking_session", uselist=False)

    booking_id = Column(
        Integer,
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False
    )

class Payment(Base):
    __tablename__ = 'payments'

    id = Column(Integer, primary_key = True, index = True)
    parking_session_id = Column(Integer, ForeignKey('parking_sessions.id'), nullable = False, unique = True)
    amount = Column(Float, nullable=False)
    payment_time = Column(DateTime(timezone = True), server_default=func.now())
    payment_method = Column(String(50), nullable = True)  # card, cash, wallet, etc.
    transaction_id = Column(String(100), unique = True, nullable = True)
    
    # Relationships
    parking_session = relationship("ParkingSession", back_populates = "payment")

class ParkingHistory(Base):
    __tablename__ = 'parking_history'

    id = Column(Integer, primary_key = True, index = True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable = False)
    vehicle_number = Column(String(20), nullable = False)
    vehicle_type = Column(String(20), nullable = False)
    entry_time = Column(DateTime(timezone = True), nullable = False)
    exit_time = Column(DateTime(timezone = True), nullable = False)
    parking_fee = Column(Float, nullable = False)
    slot_number = Column(String(10), nullable = True)
    
    # Relationships
    user = relationship("User")

class Wallet(Base):
    __tablename__ = 'wallets'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    role = Column(String(20), default="user")
    balance = Column(Float, default=0.0)
    
    user = relationship("User", back_populates="wallet")