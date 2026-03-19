from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import SessionLocal
from routers.auth import get_current_user
from model import Booking, ParkingHistory, ParkingSession, ParkingSlot, User, Vehicle, Wallet
from typing import Annotated
from routers.auth import bcrypt_context
import qrcode
import json
import os

BASE_URL = "http://localhost:8000"

router = APIRouter(
    prefix='/user',
    tags=['user']
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[User, Depends(get_current_user)]

class UpdateUserRequest(BaseModel):
    username : str | None = None
    email : str | None = None
    phone_number : str | None = None
    password : str | None = None

class RegisterVehicleRequest(BaseModel):
    vehicle_number : str
    vehicle_type : str

class BookingRequest(BaseModel):
    expected_start_time: datetime

def generate_qr_code(data: dict):
    user_id = data["user_id"]
    booking_id = data["booking_id"]
    folder = "qr_codes"
    os.makedirs(folder, exist_ok=True)

    file_name = f"qr_{user_id}_{booking_id}.png"
    file_path = os.path.join(folder, file_name)

    # Generate QR
    qr = qrcode.QRCode(
        version = 1, 
        box_size = 10, 
        border = 5
        )
    qr.add_data(json.dumps(data))
    qr.make(fit = True)
    img = qr.make_image(fill_color = "black", back_color = "white")
    img.save(file_path)

    return f"qr_codes/{file_name}"

@router.get("/profile")
async def see_profile(current_user : user_dependency):
    return {
        "user_id" :current_user.id,
        "username" : current_user.username, 
        "email" : current_user.email, 
        "phone" : current_user.phone
    }

@router.put("/profile")
async def update_user_profile(update_request : UpdateUserRequest, db : db_dependency, current_user : user_dependency):
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.role != "user":
            raise HTTPException(status_code=403, detail = "Only users can update their profile")
        if update_request.username:
            user.username = update_request.username
        if update_request.email:
            user.email = update_request.email
        if update_request.phone_number:
            user.phone = update_request.phone_number
        if update_request.password:
            user.password_hash = bcrypt_context.hash(update_request.password)
        
        db.commit()
        db.refresh(user)
        
        return {
            "user_id" :user.id,
            "username" : user.username, 
            "email" : user.email, 
            "phone" : user.phone
        }

@router.delete("/profile", status_code=204)
async def delete_user_profile(db : db_dependency, current_user : user_dependency):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code = 404, detail = "User not found")
    if user.role != "user":
            raise HTTPException(status_code=403, detail = "Only users can delete their profile")
    db.delete(user)
    db.commit()

@router.get("/my_bookings")
async def see_my_bookings(current_user : user_dependency, db : db_dependency):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code = 404, detail = "User not found")
    if user.role != "user":
            raise HTTPException(status_code=403, detail = "Only users can see their bookings")
    bookings = db.query(Booking).filter(Booking.user_id == user.id).all()
    
    return bookings

@router.get("/my_vehicles")
async def see_my_vehicles(current_user : user_dependency, db : db_dependency):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code = 404, detail = "User not found")
    if user.role != "user":
            raise HTTPException(status_code=403, detail = "Only users can see their vehicles")
    vehicles = db.query(Vehicle).filter(Vehicle.user_id == user.id).all()
    return vehicles

@router.post("/Register_vehicle")
async def register_vehicle(current_user : user_dependency, db : db_dependency, register_vehicle_request : RegisterVehicleRequest):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code = 404, detail = "User not found")
    if user.role != "user":
            raise HTTPException(status_code=403, detail = "Only users can book vehicles")
    existing_vehicle = db.query(Vehicle).filter(Vehicle.vehicle_number == register_vehicle_request.vehicle_number).first()

    if existing_vehicle:
        raise HTTPException(status_code = 400, detail = f"Vehicle {register_vehicle_request.vehicle_number} is already registered")
    vehicle = Vehicle(
        vehicle_number = register_vehicle_request.vehicle_number,
        vehicle_type = register_vehicle_request.vehicle_type,
        user_id = user.id
    )

    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)

    return {
        "user_id" : user.id,
        "username" : user.username,
        "vehicle_id" : vehicle.id,
        "vehicle_number" : vehicle.vehicle_number,
        "vehicle_type" : vehicle.vehicle_type
    }


@router.post('/book_vehicle/{vehicle_id}')
async def book_vehicle(vehicle_id : int, current_user : user_dependency, db : db_dependency, booking_request : BookingRequest):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code = 404, detail = "User not found")
    if user.role != "user":
        raise HTTPException(status_code = 403, detail = "Only users can book vehicles")
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code = 404, detail = "Vehicle not found")
    already_booked = db.query(Booking).filter(Booking.vehicle_id == vehicle_id).first()
    if already_booked:
        raise HTTPException(status_code = 400, detail = f"Vehicle {vehicle.vehicle_number} is already booked")

    booking = Booking(
        user_id = user.id,
        vehicle_id = vehicle.id,
        expected_entry_time = booking_request.expected_start_time
    )

    db.add(booking)
    db.commit()
    db.refresh(booking)

    qr_code_path = generate_qr_code(
        {
            "user_id" : user.id,
            "booking_id" : booking.id,
            "vehicle_number" : vehicle.vehicle_number,
            "vehicle_type" : vehicle.vehicle_type
        }
    )

    booking.qr_image_path = qr_code_path
    db.commit()
    db.refresh(booking)

    return {
        "booking_id" : booking.id,
        "user_id" : user.id,
        "vehicle_id" : vehicle.id,
        "vehicle_number" : vehicle.vehicle_number,
        "vehicle_type" : vehicle.vehicle_type,
        "qr_code_path" : qr_code_path
    }


@router.delete("/my_vehicles/{vehicle_id}", status_code=204)
async def remove_my_vehicle(vehicle_id : int, current_user : user_dependency, db : db_dependency):
    if current_user.role != "user":
        raise HTTPException(status_code=403, detail = "Only users can delete their vehicles")
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code = 404, detail = "Vehicle not found")
    if vehicle.user_id != current_user.id:
        raise HTTPException(status_code = 403, detail = "You are not authorized to delete this vehicle")
    db.delete(vehicle)
    db.commit()


@router.delete("/cancel_booking/{booking_id}", status_code=204)
async def cancel_booking(booking_id : int, current_user : user_dependency, db : db_dependency):
    if current_user.role != "user":
        raise HTTPException(status_code = 403, detail = "Only users can cancel their bookings")
    
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code = 404, detail = "Booking not found")
    if booking.user_id != current_user.id:
        raise HTTPException(status_code = 403, detail = "You are not authorized to cancel this booking")
    db.delete(booking)
    db.commit()

    vehicle = db.query(Vehicle).filter(Vehicle.id == booking.vehicle_id).first()
    db.commit()
    db.refresh(vehicle)

    if os.path.exists(f"qr_codes/qr_{current_user.id}_{booking.id}.png"):
        os.remove(f"qr_codes/qr_{current_user.id}_{booking.id}.png")
    else:
        print(f"QR code for booking {booking.id} not found")

    return {
        "message" : "Booking cancelled successfully",
        "vehicle_id" : vehicle.id,
        "vehicle_number" : vehicle.vehicle_number,
        "vehicle_type" : vehicle.vehicle_type
    }

@router.post("/topup_wallet")
async def topup_wallet(amount : float, current_user : user_dependency, db : db_dependency):
    if current_user.role != "user":
        raise HTTPException(status_code = 403, detail = "Only users can top up their wallet")
    user_wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    if not user_wallet:
        raise HTTPException(status_code = 404, detail = "Wallet not found")
    user_wallet.balance += amount
    db.commit()
    db.refresh(user_wallet)
    return {
        "user_id" : current_user.id,
        "username" : current_user.username,
        "wallet_balance" : user_wallet.balance
    }

@router.get("/wallet_balance")
async def wallet_balance(current_user : user_dependency, db : db_dependency):
    if current_user.role != "user":
        raise HTTPException(status_code = 403, detail = "Only users can check their wallet balance")
    user_wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    if not user_wallet:
        raise HTTPException(status_code = 404, detail = "Wallet not found")
    return {
        "user_id" : current_user.id,
        "username" : current_user.username,
        "wallet_balance" : user_wallet.balance
    }

@router.get("/slot")
async def my_slot(current_user : user_dependency, db : db_dependency):
    if current_user.role != "user":
        raise HTTPException(status_code=403, detail="Only users can check their parking slot")
    
    active_session = db.query(ParkingSession).filter(ParkingSession.user_id == current_user.id, ParkingSession.exit_time == None).first()
    if not active_session:
        return {"message" : "No active parking session", "slot": None}
    
    vehicle = db.query(Vehicle).filter(Vehicle.id == active_session.vehicle_id).first()
    slot = db.query(ParkingSlot).filter(ParkingSlot.id == active_session.slot_id).first()
    
    return {
        "slot_id" : active_session.slot_id,
        "slot_number" : slot.slot_number if slot else None,
        "parking_session_id" : active_session.id,
        "vehicle_id" : vehicle.id if vehicle else None,
        "vehicle_number" : vehicle.vehicle_number if vehicle else None,
        "vehicle_type" : vehicle.vehicle_type if vehicle else None,
        "entry_time" : active_session.entry_time
    }

@router.get("/active_slots")
async def get_user_active_slots(current_user : user_dependency, db : db_dependency):
    if current_user.role != "user":
        raise HTTPException(status_code = 403, detail = "Only users can check their parking slots")
    
    active_sessions = db.query(ParkingSession).filter(ParkingSession.user_id == current_user.id, ParkingSession.exit_time == None).all()
    
    result = []
    for session in active_sessions:
        vehicle = db.query(Vehicle).filter(Vehicle.id == session.vehicle_id).first()
        slot = db.query(ParkingSlot).filter(ParkingSlot.id == session.slot_id).first()
        
        result.append({
            "parking_session_id" : session.id,
            "slot_id" : session.slot_id,
            "slot_number" : slot.slot_number if slot else None,
            "vehicle_id" : vehicle.id if vehicle else None,
            "vehicle_number" : vehicle.vehicle_number if vehicle else None,
            "vehicle_type" : vehicle.vehicle_type if vehicle else None,
            "entry_time" : session.entry_time
        })
    
    return result

@router.get("/my_parking_history")
async def get_my_parking_history(current_user: user_dependency, db: db_dependency):
    if current_user.role != "user":
        raise HTTPException(status_code = 403, detail = "Only users can view their parking history")
    
    history = db.query(ParkingHistory).filter(ParkingHistory.user_id == current_user.id).order_by(ParkingHistory.entry_time.desc()).all()
    
    return history