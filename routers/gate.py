from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.params import File
from sqlalchemy.orm import Session
from database import SessionLocal
from typing import Annotated
from model import Booking, ParkingSession, ParkingSlot, Wallet, ParkingHistory
from routers.config import DEFAULT_ZONE, END_TIME, MAIN_ZONE, OVERDUE_PENALTY_PER_MINUTE, PER_MINUTE_FEE, DEFAULT_ZONE_SIZE
from pyzbar.pyzbar import decode
from PIL import Image
import json
import io
from PIL import Image

router = APIRouter(
    prefix='/gate',
    tags=['gate']
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

@router.post("/decode_qr")
async def decode_qr_image(file: UploadFile = File(...)):

    contents = await file.read()

    try:
        image = Image.open(io.BytesIO(contents))
    except:
        raise HTTPException(status_code = 400, detail = "Invalid image file")

    decoded_objects = decode(image)

    if not decoded_objects:
        raise HTTPException(status_code = 400, detail = "QR code not detected")

    qr_data = dict(json.loads(decoded_objects[0].data.decode("utf-8")))

    scan_result = await scan_qr_code(qr_data, db = next(get_db()))

    return scan_result

@router.post('/scan')
async def scan_qr_code(qr_data: dict, db: db_dependency):
    booking_id = qr_data.get("booking_id")
    user_id = qr_data.get("user_id")
    vehicle_number = qr_data.get("vehicle_number")
    vehicle_type = qr_data.get("vehicle_type")

    if not booking_id:
        raise HTTPException(status_code = 400, detail = "Invalid QR code data")
    
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code = 404, detail = "Booking not found")
    
    current_datetime = datetime.now(timezone.utc)
    
    # Check if it was parked before (EXIT FLOW)
    parked = db.query(ParkingSession).filter(
        ParkingSession.booking_id == booking_id,
        ParkingSession.exit_time == None
    ).first()

    if parked:
        print("Vehicle already parked, updating exit time")
        overdue_minutes = 0
        if current_datetime.time() > END_TIME:
            overdue_minutes = (current_datetime.hour - END_TIME.hour) * 60 + (current_datetime.minute - END_TIME.minute)
            if overdue_minutes < 0:
                overdue_minutes = 0
        
        total_minutes = ((current_datetime - parked.entry_time).total_seconds() / 60)
        print(f"Overdue minutes : {overdue_minutes}, Total minutes : {total_minutes}")
        stay_minutes = max(0, total_minutes - overdue_minutes)
        price = stay_minutes * PER_MINUTE_FEE
        penalty = overdue_minutes * OVERDUE_PENALTY_PER_MINUTE
        total_fee = price + penalty
        
        parked.total_fee = total_fee
        parked.exit_time = current_datetime
        parked.status = "completed"
        parked.payment_status = "pending"

        # Free up the slot
        slot = db.query(ParkingSlot).filter(ParkingSlot.id == parked.slot_id).first()
        if slot:
            slot.is_occupied = False

        # Cut amount from user's wallet
        user_wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
        if not user_wallet:
            raise HTTPException(status_code = 404, detail = "User wallet not found")
            
        if user_wallet.balance < total_fee:
            raise HTTPException(
                status_code = 402, 
                detail = f"Insufficient wallet balance. Required: {total_fee}, Available: {user_wallet.balance}"
            )
            
        user_wallet.balance -= total_fee
        
        # Add to admin wallet
        admin_wallet = db.query(Wallet).filter(Wallet.role == "admin").first()
        if admin_wallet:
            admin_wallet.balance += total_fee

        parked.payment_status = "Paid"

        # Create history record and delete parking session
        parking_slot = db.query(ParkingSlot).filter(ParkingSlot.id == parked.slot_id).first()

        history = ParkingHistory(
            user_id = user_id,
            vehicle_number = vehicle_number,
            vehicle_type = vehicle_type,
            entry_time = parked.entry_time,
            exit_time =  current_datetime,
            parking_fee = total_fee,
            slot_number = parking_slot.slot_number if parking_slot else None
        )
        exit_time = parked.exit_time
        db.delete(parked)

        db.add(history)
        db.commit()

        return {
            "message" : "Vehicle exit recorded successfully",
            "booking_id" : booking_id,
            "user_id" : user_id,
            "vehicle_number" : vehicle_number,
            "vehicle_type" : vehicle_type,
            "total_fee" : total_fee,
            "exit_time" : exit_time,
            "slot_number" : slot.slot_number if slot else None
        }

    # ENTRY FLOW - Check if booking is already used
    
    # Check availability of slot and assign if available
    if current_datetime < booking.expected_entry_time :
        zone = DEFAULT_ZONE # early -> go to default zone
    else:
        zone = MAIN_ZONE
    print(zone,"",vehicle_type)
    available = db.query(ParkingSlot).filter(
        ParkingSlot.vehicle_type == vehicle_type,
        ParkingSlot.is_occupied == False,
        ParkingSlot.is_active == True,
        ParkingSlot.zone == zone
    ).order_by(ParkingSlot.id).first()
    
    if not available:
        available = db.query(ParkingSlot).filter(
            ParkingSlot.vehicle_type == vehicle_type,
            ParkingSlot.is_occupied == False,
            ParkingSlot.is_active == True
        ).order_by(ParkingSlot.id).first()

    if not available:
        raise HTTPException(
            status_code = 404, 
            detail = f"No available parking slot for vehicle type {vehicle_type}"
        )
    print(available.id,available)
    # Create parking session
    parking_session = ParkingSession(
        booking_id = booking.id,
        user_id = user_id,
        vehicle_id = booking.vehicle_id,
        slot_id = available.id,
        entry_time = current_datetime,
        status = "active",
        payment_status = "pending"
    )
    
    # Update slot occupancy
    available.is_occupied = True
    
    # Mark booking as used
    booking.is_used = True
    
    db.add(parking_session)
    db.commit()
    
    return {
        "message" : "Entry recorded successfully",
        "booking_id" : booking_id,
        "user_id" : user_id,
        "vehicle_number" : vehicle_number,
        "vehicle_type" : vehicle_type,
        "slot_number" : available.slot_number,
        "entry_time" : current_datetime
    }