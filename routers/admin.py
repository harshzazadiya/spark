import os
from datetime import datetime, time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import SessionLocal
from routers.auth import get_current_user
from model import Booking, ParkingHistory, ParkingSession, ParkingSlot, User, Vehicle, Wallet
from typing import Annotated, Optional, List 
from routers.config import DEFAULT_ZONE, END_TIME, MAIN_ZONE, OVERDUE_PENALTY_PER_MINUTE, PER_MINUTE_FEE, DEFAULT_ZONE_SIZE
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix='/admin',
    tags=['admin']
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[User, Depends(get_current_user)]

def admin_required(current_user : user_dependency):
    if current_user.role != "admin":
        raise HTTPException(status_code = 403, detail = "Not authorized")
    return current_user

admin_dependency = Annotated[User, Depends(admin_required)]

class DefaultValues(BaseModel):
    start_time : time 
    end_time : time
    default_zone : str 
    default_zone_size : int
    main_zone : str
    per_minute_fee : float 
    overdue_grace_period_minutes : int 
    overdue_penalty_per_minute : float 

class add_parking_spot_request(BaseModel):
    vehicle_type : str
    count : int
    zone : str

class RemoveParkingSpotsRequest(BaseModel):
    zone: str
    start_number: int
    count: int

class UpdateSlot(BaseModel):
    slot_number : Optional[str] = None
    vehicle_type : Optional[str] = None
    zone : Optional[str] = None
    is_occupied : Optional[bool] = None
    is_active : Optional[bool] = None

@router.get("/dashboard")
async def admin_dashboard(db : db_dependency, current_user : admin_dependency):

    total_users = db.query(User).filter(User.role != "admin", User.is_active == True).count()
    total_vehicles_registered = db.query(Vehicle).count()
    total_slots = db.query(ParkingSlot).count()
    occupied_slots = db.query(ParkingSlot).filter(ParkingSlot.is_occupied == True).count()
    available_slots = db.query(ParkingSlot).filter(ParkingSlot.is_occupied == False).count()
    current_parking = db.query(ParkingSlot).filter(ParkingSlot.is_occupied == True).count()
    total_bookings = db.query(Booking).count()
    total_users_who_has_used_parking = db.query(ParkingHistory.user_id).distinct().count()
    total_revenue = db.query(Wallet).filter(Wallet.role == "admin").with_entities(func.sum(Wallet.balance)).scalar() or 0.0
    return {
        "total_users" : total_users,
        "total_users_who_has_used_parking" : total_users_who_has_used_parking,
        "total_vehicles_registered" : total_vehicles_registered,
        "total_slots" : total_slots,
        "occupied_slots" : occupied_slots,
        "current_parking" : current_parking,
        "available_slots" : available_slots,
        "total_bookings" : total_bookings,
        "total_revenue" : total_revenue
    }

@router.get('/users')
async def get_users(db: db_dependency, current_user: admin_dependency):
    users = db.query(User).filter(User.role != "admin", User.is_active == True).order_by(User.id).all()
    return users

@router.get('/bookings')
async def get_bookings(db: db_dependency, current_user: admin_dependency):
    bookings = db.query(Booking).order_by(Booking.id).all()
    return bookings

@router.get('/vehicles')
async def get_vehicles(db: db_dependency, current_user: admin_dependency):
    vehicles = db.query(Vehicle).order_by(Vehicle.id).all()
    return vehicles

@router.delete('/users/{user_id}')
async def delete_user(user_id: int, db: db_dependency, current_user: admin_dependency):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code = 404, detail = 'User not found')
    if user.role == "admin":
        raise HTTPException(status_code = 403, detail = 'Cannot delete admin user')
    sessions = db.query(ParkingSession).filter(ParkingSession.user_id == user_id).all()
    if sessions:
        raise HTTPException(status_code = 400, detail = 'Cannot delete user with active parking sessions')
    vehicles = db.query(Vehicle).filter(Vehicle.user_id == user_id).all()
    for vehicle in vehicles:
        if vehicle.user_id == user_id:
            bookings = db.query(Booking).filter(Booking.vehicle_id == vehicle.id).all()
            for booking in bookings:
                if booking.qr_image_path:
                    file_path = booking.qr_image_path
                    if os.path.exists(file_path):
                        os.remove(file_path)
                db.delete(booking)
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    if wallet:
        db.delete(wallet)
    user.is_active = False
    db.commit()
    return {'message': 'User deleted successfully'}

@router.delete('/vehicles/{vehicle_id}')
async def delete_vehicle(vehicle_id: int, db: db_dependency, current_user: admin_dependency):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    sessions = db.query(ParkingSession).filter(ParkingSession.vehicle_id == vehicle_id).all()
    if sessions:
        raise HTTPException(status_code = 400, detail = 'Cannot delete vehicle with active parking sessions')
    if not vehicle:
        raise HTTPException(status_code = 404, detail = 'Vehicle not found')
    bookings = db.query(Booking).filter(Booking.vehicle_id == vehicle_id).all()
    for booking in bookings:
        if booking.qr_image_path:
            file_path = booking.qr_image_path
            if os.path.exists(file_path):
                os.remove(file_path)
        db.delete(booking)
    db.delete(vehicle)
    db.commit()
    return {'message': 'Vehicle deleted successfully'}

@router.post("/parking_spots")
async def add_parking_spots(db : db_dependency, current_user : admin_dependency, add_spots : add_parking_spot_request):
    if add_spots.count <= 0:
        raise HTTPException(status_code = 400, detail = "Number of spots must be greater than 0")
    if add_spots.vehicle_type not in ["Two_Wheeler", "Four_Wheeler"]:
        raise HTTPException(status_code = 400,detail = f"Invalid vehicle type : {add_spots.vehicle_type}. Must be 'Two_Wheeler' or 'Four_Wheeler'")
    if not add_spots.zone or len(add_spots.zone.strip()) == 0:
        raise HTTPException(status_code = 400,detail = "Zone cannot be empty")
    
    zone = add_spots.zone.strip().upper()
    
    try:
        db.begin()
        
        existing_slots = db.query(ParkingSlot).filter(ParkingSlot.zone == zone).count()
        
        new_slot_numbers = []
        for i in range(add_spots.count):
            slot_number = f"{zone}-{existing_slots + i + 1}"
            existing = db.query(ParkingSlot).filter(ParkingSlot.slot_number == slot_number).first()
            
            if existing:
                raise HTTPException(status_code = 409,detail = f"Slot number {slot_number} already exists. Possible data inconsistency.")
            
            new_slot_numbers.append(slot_number)
        
        new_spots = []
        for i, slot_number in enumerate(new_slot_numbers):
            new_spot = ParkingSlot(
                slot_number = slot_number,
                vehicle_type = add_spots.vehicle_type,
                zone = zone,
                is_occupied = False,
                is_active = True
            )
            db.add(new_spot)
            new_spots.append(new_spot)
        
        await ensure_default_zone_exists(db)
        
        db.commit()
        
        return {
            "message": f"Successfully added {add_spots.count} parking spots",
            "details": {
                "zone": zone,
                "vehicle_type": add_spots.vehicle_type,
                "count": add_spots.count,
                "slot_numbers": new_slot_numbers,
                "total_slots_in_zone": existing_slots + add_spots.count
            }
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code = 500, detail = f"Failed to add parking spots: {str(e)}")

async def ensure_default_zone_exists(db: Session):
    default_zone_exists = db.query(ParkingSlot).filter(ParkingSlot.zone == DEFAULT_ZONE).first()
    
    if default_zone_exists:
        return
    
    default_spots = []
    half_size = DEFAULT_ZONE_SIZE // 2
    
    for i in range(DEFAULT_ZONE_SIZE):
        if i < half_size:
            vehicle_type = "Four_Wheeler"
        else:
            vehicle_type = "Two_Wheeler"
        
        slot_number = f"{DEFAULT_ZONE}-{i + 1}"
        
        existing = db.query(ParkingSlot).filter(ParkingSlot.slot_number == slot_number).first()
        
        if existing:
            continue  
        
        new_spot = ParkingSlot(
            slot_number = slot_number,
            vehicle_type = vehicle_type,
            zone = DEFAULT_ZONE,
            is_occupied = False,
            is_active = True
        )
        db.add(new_spot)
        default_spots.append(new_spot)
    
    if default_spots:
        logger.info(f"Added {len(default_spots)} default parking spots to zone {DEFAULT_ZONE}")

@router.post("/parking_spots/bulk")
async def add_parking_spots_bulk(db : db_dependency, current_user : admin_dependency, zones : List[add_parking_spot_request]):
    """
    Add parking spots to multiple zones in one request.
    """
    if len(zones) > 10:  # Reasonable limit
        raise HTTPException(status_code = 400, detail = "Cannot process more than 10 zone requests at once")
    
    results = []
    errors = []
    
    for zone_request in zones:
        try:
            zone = zone_request.zone.strip().upper()
            existing_slots = db.query(ParkingSlot).filter(ParkingSlot.zone == zone).count()
            
            new_slot_numbers = []
            for i in range(zone_request.count):
                slot_number = f"{zone}-{existing_slots + i + 1}"
                
                existing = db.query(ParkingSlot).filter(ParkingSlot.slot_number == slot_number).first()
                
                if existing:
                    errors.append({
                        "zone" : zone,
                        "slot_number" : slot_number,
                        "error" : "Slot number already exists"
                    })
                    continue
                
                new_spot = ParkingSlot(
                    slot_number=slot_number,
                    vehicle_type=zone_request.vehicle_type,
                    zone=zone
                )
                db.add(new_spot)
                new_slot_numbers.append(slot_number)
            
            results.append({
                "zone" : zone,
                "vehicle_type" : zone_request.vehicle_type,
                "requested" : zone_request.count,
                "added" : len(new_slot_numbers),
                "slot_numbers" : new_slot_numbers
            })
            
        except Exception as e:
            errors.append({
                "zone" : zone_request.zone,
                "error" : str(e)
            })
    
    await ensure_default_zone_exists(db)
    
    db.commit()
    
    return {
        "message" : f"Processed {len(zones)} zone requests",
        "results" : results,
        "errors" : errors if errors else None
    }

@router.delete("/parking_spots")
async def remove_parking_spots(remove_spots : RemoveParkingSpotsRequest, db : db_dependency, current_user : admin_dependency):
    slots_to_delete = [
        f"{remove_spots.zone}-{i}"
        for i in range(remove_spots.start_number,
                       remove_spots.start_number + remove_spots.count)
    ]

    spots = db.query(ParkingSlot).filter(ParkingSlot.slot_number.in_(slots_to_delete), ParkingSlot.is_occupied == False).all()

    deleted_count = len(spots)

    for spot in spots:
        db.delete(spot)

    db.commit()

    return {
        "message" : f"{deleted_count} parking spots deleted",
        "deleted_count" : deleted_count,
        "slots_requested" : slots_to_delete
    }

@router.get("/parking_slots")
async def get_parking_slots(db: db_dependency, current_user: user_dependency):
    parking_slots = db.query(ParkingSlot).order_by(ParkingSlot.id).all()
    return parking_slots

@router.delete("/parking_slots/{slot_id}")
async def delete_parking_slot(slot_id : int, db : db_dependency, current_user : admin_dependency):
    slot = db.query(ParkingSlot).filter(ParkingSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code = 404, detail = 'Parking slot not found')
    if slot.is_occupied:
        raise HTTPException(status_code = 400, detail = 'Cannot delete occupied parking slot')
    db.delete(slot)
    db.commit()
    return {"message" : f"Parking slot with id {slot_id} deleted successfully"}

@router.get("/parking_slots/{slot_id}")
async def get_parking_slot(slot_id : int, db : db_dependency, current_user : admin_dependency):
    slot = db.query(ParkingSlot).filter(ParkingSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code = 404, detail = 'Parking slot not found')
    return slot

@router.delete("/parking_slots/zone/{zone}")
async def delete_parking_slots_by_zone(zone : str, db : db_dependency, current_user : admin_dependency):
    slots_to_delete = db.query(ParkingSlot).filter(ParkingSlot.zone == zone).all()
    if not slots_to_delete:
        raise HTTPException(status_code = 404, detail = f'No parking slots found in zone {zone}')
    for slot in slots_to_delete:
        db.delete(slot)
    db.commit()
    return {"message" : f"All parking slots in zone {zone} deleted successfully"}

@router.delete("/parking_slots/vehicle_type/{vehicle_type}")
async def delete_parking_slots_by_vehicle_type(vehicle_type : str, db : db_dependency, current_user : admin_dependency):
    slots_to_delete = db.query(ParkingSlot).filter(ParkingSlot.vehicle_type == vehicle_type).all()
    if not slots_to_delete:
        raise HTTPException(status_code = 404, detail = f'No parking slots found for vehicle type {vehicle_type}')
    for slot in slots_to_delete:
        db.delete(slot)
    db.commit()
    return {"message" : f"All parking slots for vehicle type {vehicle_type} deleted successfully"}

@router.delete("/booking/{booking_id}")
async def delete_booking(booking_id : int, db : db_dependency, current_user : admin_dependency):

    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail='Booking not found')
    is_active_session = db.query(ParkingSession).filter(ParkingSession.booking_id == booking_id).first()
    if is_active_session:
        raise HTTPException(status_code=400, detail='Cannot delete booking with active parking session')
    if booking.qr_image_path:
        file_path = booking.qr_image_path

        if os.path.exists(file_path):
            os.remove(file_path)

    db.delete(booking)
    db.commit()

    return {"message": f"Booking with id {booking_id} deleted successfully"}

@router.put("/change_default_values")
async def change_default_values(db : db_dependency, current_user : admin_dependency, default_values : DefaultValues):

    global START_TIME, END_TIME, DEFAULT_ZONE, DEFAULT_ZONE_SIZE, MAIN_ZONE, PER_MINUTE_FEE, OVERDUE_GRACE_PERIOD_MINUTES, OVERDUE_PENALTY_PER_MINUTE

    START_TIME = default_values.start_time
    END_TIME = default_values.end_time
    DEFAULT_ZONE = default_values.default_zone
    DEFAULT_ZONE_SIZE = default_values.default_zone_size
    MAIN_ZONE = default_values.main_zone
    PER_MINUTE_FEE = default_values.per_minute_fee
    OVERDUE_GRACE_PERIOD_MINUTES = default_values.overdue_grace_period_minutes
    OVERDUE_PENALTY_PER_MINUTE = default_values.overdue_penalty_per_minute
    return {
        "message" : "Default values updated successfully", 
        "start_time" : START_TIME, 
        "end_time" : END_TIME, 
        "default_zone" : DEFAULT_ZONE,
        "default_zone_size" : DEFAULT_ZONE_SIZE,
        "main_zone" : MAIN_ZONE,
        "per_minute_fee" : PER_MINUTE_FEE,
        "overdue_grace_period_minutes" : OVERDUE_GRACE_PERIOD_MINUTES,
        "overdue_penalty_per_minute" : OVERDUE_PENALTY_PER_MINUTE
        }

@router.post("/topup_wallet")
async def topup_wallet(amount : float, admin : admin_dependency, db : db_dependency):
    if admin.role != "admin":
        raise HTTPException(status_code = 403, detail = "Only admins can top up user wallets")
    user_wallet = db.query(Wallet).filter(Wallet.user_id == admin.id).first()
    if not user_wallet:
        raise HTTPException(status_code = 404, detail = "Wallet not found")
    user_wallet.balance += amount
    db.commit()
    db.refresh(user_wallet)
    return {
        "user_id" : admin.id,
        "username" : admin.username,
        "wallet_balance" : user_wallet.balance
    }

@router.get("/wallet_balance")
async def wallet_balance(admin : admin_dependency, db : db_dependency):
    user_wallet = db.query(Wallet).filter(Wallet.user_id == admin.id).first()
    if not user_wallet:
        raise HTTPException(status_code = 404, detail = "Wallet not found")
    return {
        "Admin_id" : admin.id,
        "username" : admin.username,
        "wallet_balance" : user_wallet.balance
    }

@router.put("/parking_slot/{slot_id}")
async def update_parking_slot(slot_id: int, db: db_dependency, current_user: admin_dependency, update_slot: UpdateSlot):
    slot = db.query(ParkingSlot).filter(ParkingSlot.id == slot_id).first()
    
    if not slot:
        raise HTTPException(status_code=404, detail='Parking slot not found')
    
    if update_slot.slot_number is not None and update_slot.slot_number != slot.slot_number:
        existing_slot = db.query(ParkingSlot).filter(ParkingSlot.slot_number == update_slot.slot_number).first()
        if existing_slot:
            raise HTTPException(status_code=400, detail=f"Slot number {update_slot.slot_number} already exists")

    if update_slot.slot_number is not None:
        slot.slot_number = update_slot.slot_number
    if update_slot.vehicle_type is not None:
        slot.vehicle_type = update_slot.vehicle_type
    if update_slot.zone is not None:
        slot.zone = update_slot.zone
    if update_slot.is_occupied is not None:
        slot.is_occupied = update_slot.is_occupied
    if update_slot.is_active is not None:
        slot.is_active = update_slot.is_active
    
    db.commit()
    db.refresh(slot)
    
    return slot

@router.get("/history")
async def get_parking_history(db : db_dependency, current_user : admin_dependency):
    history = db.query(ParkingHistory).order_by(ParkingHistory.id.desc()).all()
    return history
    