import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time as time_module
from datetime import timedelta

# ==================== CONFIGURATION ====================
API_BASE_URL = "http://spark_backend:8000"

# ==================== SESSION STATE INITIALIZATION ====================
def init_session_state():
    """Initialize all session state variables"""
    if 'token' not in st.session_state:
        st.session_state.token = None
    if 'user_info' not in st.session_state:
        st.session_state.user_info = None
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'role' not in st.session_state:
        st.session_state.role = None
    if 'page' not in st.session_state:
        st.session_state.page = "Login"
    if 'refresh_data' not in st.session_state:
        st.session_state.refresh_data = False
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = time_module.time()
    if 'parking_slots_cache' not in st.session_state:
        st.session_state.parking_slots_cache = None
    if 'selected_booking' not in st.session_state:
        st.session_state.selected_booking = None
    if 'admin_nested_tab' not in st.session_state:
        st.session_state.admin_nested_tab = "Overview"
    if 'slot_filter_zone' not in st.session_state:
        st.session_state.slot_filter_zone = "All"
    if 'slot_filter_type' not in st.session_state:
        st.session_state.slot_filter_type = "All"
    if 'show_qr' not in st.session_state:
        st.session_state.show_qr = {}

# ==================== API HELPER FUNCTIONS ====================
def api_request(method, endpoint, data=None, params=None, require_auth=True):
    """Make API requests with proper headers"""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    
    if require_auth and st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    
    try:
        if method.lower() == "get":
            response = requests.get(url, headers=headers, params=params)
        elif method.lower() == "post":
            response = requests.post(url, headers=headers, json=data)
        elif method.lower() == "put":
            response = requests.put(url, headers=headers, json=data)
        elif method.lower() == "delete":
            if data:
                response = requests.request("DELETE", url, headers=headers, json=data)
            else:
                response = requests.delete(url, headers=headers)
        else:
            return None, "Invalid method"
        
        if response.status_code in [200, 201]:
            return response.json(), None
        elif response.status_code == 401:
            st.session_state.authenticated = False
            st.session_state.token = None
            st.session_state.page = "Login"
            return None, "Session expired. Please login again."
        else:
            try:
                error_detail = response.json().get('detail', 'Unknown error')
            except:
                error_detail = response.text or f"Error {response.status_code}"
            return None, error_detail
    except requests.exceptions.ConnectionError:
        return None, f"Cannot connect to server at {API_BASE_URL}"
    except Exception as e:
        return None, str(e)

# ==================== AUTHENTICATION FUNCTIONS ====================
def login(username, password):
    """Login user and get token"""
    url = f"{API_BASE_URL}/auth/token"
    
    try:
        response = requests.post(
            url,
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code == 200:
            result = response.json()
            st.session_state.token = result["access_token"]
            
            user_info, user_error = api_request("get", "/auth/me", require_auth=True)
            if not user_error:
                st.session_state.user_info = user_info
                st.session_state.authenticated = True
                st.session_state.role = user_info.get('role', 'user')
                st.session_state.page = "Dashboard"
                st.success("Login successful!")
                st.rerun()
                return True
            else:
                st.error(f"Failed to get user info: {user_error}")
                return False
        else:
            try:
                error_detail = response.json().get('detail', 'Unknown error')
            except:
                error_detail = response.text or f"Error {response.status_code}"
            st.error(f"Login failed: {error_detail}")
            return False
    except Exception as e:
        st.error(f"Login failed: {str(e)}")
        return False

def register(username, email, password, phone_number, is_admin=False):
    """Register new user"""
    data = {
        "username": username,
        "email": email,
        "password": password,
        "phone_number": phone_number
    }
    
    endpoint = "/auth/admin" if is_admin else "/auth/user"
    result, error = api_request("post", endpoint, data=data, require_auth=False)
    
    if error:
        st.error(f"Registration failed: {error}")
        return False
    
    if result:
        st.success("Registration successful! Please login.")
        return True
    return False

def logout():
    """Logout user"""
    st.session_state.token = None
    st.session_state.user_info = None
    st.session_state.authenticated = False
    st.session_state.role = None
    st.session_state.page = "Login"
    st.session_state.parking_slots_cache = None
    st.rerun()

# ==================== USER FUNCTIONS ====================
def get_user_profile():
    """Get current user profile"""
    return api_request("get", "/user/profile")

def get_user_active_slots():
    """Get all active parking slots for the current user"""
    return api_request("get", "/user/active_slots")

def update_user_profile(username, email, phone, password=None):
    """Update user profile"""
    data = {
        "username": username,
        "email": email,
        "phone_number": phone
    }
    if password:
        data["password"] = password
    return api_request("put", "/user/profile", data=data)

def get_user_vehicles():
    """Get user's vehicles"""
    return api_request("get", "/user/my_vehicles")

def register_vehicle(vehicle_number, vehicle_type):
    """Register a new vehicle"""
    data = {
        "vehicle_number": vehicle_number,
        "vehicle_type": vehicle_type
    }
    return api_request("post", "/user/Register_vehicle", data=data)

def delete_vehicle(vehicle_id):
    """Delete a vehicle"""
    return api_request("delete", f"/user/my_vehicles/{vehicle_id}")

def get_user_bookings():
    """Get user's bookings"""
    return api_request("get", "/user/my_bookings")

def book_vehicle(vehicle_id, expected_start_time):
    """Book a vehicle"""
    data = {
        "expected_start_time": expected_start_time.isoformat()
    }
    return api_request("post", f"/user/book_vehicle/{vehicle_id}", data=data)

def cancel_booking(booking_id):
    """Cancel a booking"""
    return api_request("delete", f"/user/cancel_booking/{booking_id}")

def get_user_wallet_balance():
    """Get user's wallet balance"""
    return api_request("get", "/user/wallet_balance")

def topup_user_wallet(amount):
    """Top up user wallet"""
    return api_request("post", f"/user/topup_wallet?amount={amount}")

def get_user_active_slot():
    """Get user's active parking slot"""
    return api_request("get", "/user/slot")

def get_my_parking_history():
    return api_request("get", "/user/my_parking_history")
# ==================== ADMIN FUNCTIONS ====================
def get_admin_dashboard():
    """Get admin dashboard stats"""
    return api_request("get", "/admin/dashboard")

def get_all_users():
    """Get all users"""
    return api_request("get", "/admin/users")

def delete_user(user_id):
    """Delete a user"""
    return api_request("delete", f"/admin/users/{user_id}")

def get_all_vehicles():
    """Get all vehicles"""
    return api_request("get", "/admin/vehicles")

def delete_vehicle_admin(vehicle_id):
    """Delete a vehicle (admin)"""
    return api_request("delete", f"/admin/vehicles/{vehicle_id}")

def get_all_bookings():
    """Get all bookings"""
    return api_request("get", "/admin/bookings")

def delete_booking(booking_id):
    """Delete a booking"""
    return api_request("delete", f"/admin/booking/{booking_id}")

def get_all_parking_slots():
    """Get all parking slots"""
    return api_request("get", "/admin/parking_slots")

def add_parking_spots(vehicle_type, count, zone):
    """Add parking spots"""
    data = {
        "vehicle_type": vehicle_type,
        "count": count,
        "zone": zone
    }
    return api_request("post", "/admin/parking_spots", data=data)

def remove_parking_spots(data):
    """Remove parking spots"""
    return api_request("delete", "/admin/parking_spots", data=data)

def delete_parking_slot(slot_id):
    """Delete a parking slot"""
    return api_request("delete", f"/admin/parking_slots/{slot_id}")

def update_parking_slot(slot_id, update_data):
    """Update a parking slot"""
    return api_request("put", f"/admin/parking_slot/{slot_id}", data=update_data)

def change_default_values(values):
    """Change system default values"""
    return api_request("put", "/admin/change_default_values", data=values)

def get_admin_wallet_balance():
    """Get admin wallet balance"""
    return api_request("get", "/admin/wallet_balance")

def topup_admin_wallet(amount):
    """Top up admin wallet"""
    return api_request("post", f"/admin/topup_wallet?amount={amount}")

def get_parking_history():
    """Get parking history (admin)"""
    return api_request("get", "/admin/history")

# ==================== GATE FUNCTIONS ====================
def scan_qr_code(qr_data):
    """Process QR code scan (entry/exit)"""
    return api_request("post", "/gate/scan", data=qr_data)

# ==================== VISUALIZATION FUNCTIONS ====================
def display_parking_grid(slots_data, user_bookings=None, current_user_id=None):
    """Display parking slots as a grid of colored boxes"""
    
    if not slots_data:
        st.info("No parking slots configured")
        return
    
    # Sort slots by ID for consistent ordering
    slots_data = sorted(slots_data, key=lambda x: x.get('id', 0))
    
    # Get all user assigned slots
    user_slot_ids = set()

    if user_bookings and isinstance(user_bookings, list):
        for slot in user_bookings:
            if isinstance(slot, dict):
                sid = slot.get("slot_id") or slot.get("id")
                if sid:
                    user_slot_ids.add(sid)
    
    # Group slots by zone
    zones = {}
    for slot in slots_data:
        zone = slot.get('zone', 'DEFAULT')
        if zone not in zones:
            zones[zone] = []
        zones[zone].append(slot)
    
    # Display each zone
    for zone_name, zone_slots in zones.items():
        st.markdown(f"### 🅿️ Zone {zone_name}")
        
        # Create grid layout
        cols_per_row = 5
        slot_rows = [zone_slots[i:i + cols_per_row] for i in range(0, len(zone_slots), cols_per_row)]
        
        for row_idx, row_slots in enumerate(slot_rows):
            cols = st.columns(cols_per_row)
            for col_idx, slot in enumerate(row_slots):
                with cols[col_idx]:
                    slot_id = slot.get('id')
                    slot_number = slot.get('slot_number', 'Unknown')
                    vehicle_type = slot.get('vehicle_type', 'N/A')
                    is_occupied = slot.get('is_occupied', False)
                    is_active = slot.get('is_active', True)
                    
                    # Determine color and status text
                    if not is_active:
                        color = "#ff4444"  # Red for inactive
                        status = "INACTIVE"
                        text_color = "white"
                        border = "2px solid #333"
                    elif slot_id in user_slot_ids:
                        color = "#ffaa00"  # Bright yellow for user's assigned slot
                        status = "YOUR SLOT"  # Show as occupied to others, but yellow for user
                        text_color = "black"
                        border = "3px solid #ff5500"  # Orange border for emphasis
                    elif is_occupied:
                        color = "#aaaaaa"  # Grey for occupied by others
                        status = "OCCUPIED"
                        text_color = "white"
                        border = "2px solid #333"
                    else:
                        color = "#44aa44"  # Green for available
                        status = "AVAILABLE"
                        text_color = "white"
                        border = "2px solid #333"
                    
                    # Create box with enhanced styling for user's slot
                    box_style = f"""
                        background-color: {color};
                        padding: 10px;
                        border-radius: 5px;
                        margin: 5px 0;
                        text-align: center;
                        color: {text_color};
                        font-weight: bold;
                        border: {border};
                    """
                    
                    if slot_id in user_slot_ids:
                        box_style += "box-shadow: 0 0 10px #ffaa00;"
                    
                    st.markdown(f"""
                    <div style="{box_style}">
                        <div style="font-size: 14px;">{slot_number}</div>
                        <div style="font-size: 10px;">{vehicle_type}</div>
                        <div style="font-size: 10px; margin-top: 5px;">{status}</div>
                    </div>
                    """, unsafe_allow_html=True)
        
        st.markdown("---")
    
    # Legend
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("""
        <div style="display: flex; align-items: center;">
            <div style="width: 20px; height: 20px; background-color: #44aa44; margin-right: 10px; border: 2px solid #333;"></div>
            <span>Available</span>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div style="display: flex; align-items: center;">
            <div style="width: 20px; height: 20px; background-color: #aaaaaa; margin-right: 10px; border: 2px solid #333;"></div>
            <span>Occupied</span>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div style="display: flex; align-items: center;">
            <div style="width: 20px; height: 20px; background-color: #ffaa00; margin-right: 10px; border: 3px solid #ff5500;"></div>
            <span>Your Slot</span>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown("""
        <div style="display: flex; align-items: center;">
            <div style="width: 20px; height: 20px; background-color: #ff4444; margin-right: 10px; border: 2px solid #333;"></div>
            <span>Inactive</span>
        </div>
        """, unsafe_allow_html=True)
        
def refresh_parking_data():
    """Refresh parking slots data"""
    slots, error = get_all_parking_slots()
    if not error:
        st.session_state.parking_slots_cache = slots
        st.session_state.last_refresh = time_module.time()
    return slots, error

# ==================== PAGE FUNCTIONS ====================
def login_page():
    """Login page"""
    st.title("🔐 Smart Parking System Login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        try:
            st.image("SPARK.png", width=150)
        except:
            st.markdown("# 🅿️")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        col1, col2 = st.columns(2)
        
        with col1:
            submitted = st.form_submit_button("Login", use_container_width=True, type="primary")
        with col2:
            if st.form_submit_button("Register", use_container_width=True):
                st.session_state.page = "Register"
                st.rerun()
        
        if submitted:
            if username and password:
                login(username, password)
            else:
                st.error("Please enter username and password")

def register_page():
    """Registration page"""
    st.title("📝 Create New Account")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        try:
            st.image("SPARK.png", width=100)
        except:
            st.markdown("# 📝")
    
    with st.form("register_form"):
        username = st.text_input("Username*")
        email = st.text_input("Email*")
        password = st.text_input("Password*", type="password")
        confirm_password = st.text_input("Confirm Password*", type="password")
        phone = st.text_input("Phone Number*")
        
        role = st.radio("Account Type", ["User", "Admin"], horizontal=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Register", use_container_width=True, type="primary"):
                if password != confirm_password:
                    st.error("Passwords do not match")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters")
                elif username and email and password and phone:
                    is_admin = (role == "Admin")
                    if register(username, email, password, phone, is_admin):
                        st.session_state.page = "Login"
                        st.rerun()
                else:
                    st.error("Please fill all required fields")
        with col2:
            if st.form_submit_button("Back to Login", use_container_width=True):
                st.session_state.page = "Login"
                st.rerun()

def user_dashboard():
    """User dashboard"""
    st.title(f"👤 Welcome, {st.session_state.user_info.get('username', 'User')}")
    
    # Auto-refresh every 30 seconds
    if time_module.time() - st.session_state.last_refresh > 30:
        refresh_parking_data()
    
    # Get user data
    profile, profile_error = get_user_profile()
    vehicles, vehicles_error = get_user_vehicles()
    bookings, bookings_error = get_user_bookings()
    wallet_data, wallet_error = get_user_wallet_balance()
    active_slots, active_slots_error = get_user_active_slots()  # Get all active slots
    
    wallet_balance = wallet_data.get('wallet_balance', 0) if wallet_data else 0
    
    # Calculate active bookings correctly
    active_bookings = 0
    if bookings:
        for booking in bookings:
            if booking.get('is_active'):
                active_bookings += 1
    
    # Display stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Wallet Balance", f"₹{wallet_balance:.2f}")
    with col2:
        st.metric("Total Vehicles", len(vehicles) if vehicles else 0)
    with col3:
        st.metric("Active Bookings", active_bookings)
    with col4:
        if active_slots and not active_slots_error and len(active_slots) > 0:
            slot_numbers = [slot.get('slot_number', 'None') for slot in active_slots if slot.get('slot_number')]
            display_text = ", ".join(slot_numbers) if slot_numbers else "None"
            st.metric("Your Slots", display_text)
        else:
            st.metric("Your Slots", "None")
    
    tabs = st.tabs(["🅿️ Parking Grid", "🚗 My Vehicles", "📅 My Bookings", "👤 Profile", "💰 Wallet", "📊 History"])
    
    # Tab 1: Parking Grid
    with tabs[0]:
        st.subheader("🅿️ Live Parking Status")
        
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🔄 Refresh", use_container_width=True):
                refresh_parking_data()
            st.caption(f"Last updated: {datetime.fromtimestamp(st.session_state.last_refresh).strftime('%H:%M:%S')}")
        
        # Get parking slots data
        slots, error = refresh_parking_data() if st.session_state.parking_slots_cache is None else (st.session_state.parking_slots_cache, None)
        
        if error:
            st.error(f"Failed to load parking data: {error}")
        else:
            # Pass all active slots to the display function
            display_parking_grid(slots, active_slots)
    
    # Tab 2: My Vehicles
    with tabs[1]:
        st.subheader("🚗 My Vehicles")
        
        with st.expander("➕ Register New Vehicle", expanded=False):
            with st.form("add_vehicle_form"):
                vehicle_number = st.text_input("Vehicle Number (e.g., GJ05 XY 1234)")
                vehicle_type = st.selectbox("Vehicle Type", ["Two_Wheeler", "Four_Wheeler"])
                
                if st.form_submit_button("Register Vehicle", use_container_width=True):
                    if vehicle_number:
                        result, error = register_vehicle(vehicle_number, vehicle_type)
                        if error:
                            st.error(error)
                        else:
                            st.success(f"Vehicle {vehicle_number} registered successfully!")
                            st.rerun()
                    else:
                        st.error("Please enter vehicle number")
        
        if vehicles:
            df = pd.DataFrame(vehicles)
            if not df.empty:
                display_df = df[['id', 'vehicle_number', 'vehicle_type', 'created_at']].copy()
                display_df.columns = ['ID', 'Vehicle Number', 'Type', 'Registered On']
                if 'Registered On' in display_df.columns:
                    display_df['Registered On'] = pd.to_datetime(display_df['Registered On']).dt.strftime('%Y-%m-%d %H:%M')
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                with st.form("delete_vehicle_form"):
                    vehicle_to_delete = st.selectbox(
                        "Select vehicle to delete",
                        options=df['id'].tolist(),
                        format_func=lambda x: f"{df[df['id']==x]['vehicle_number'].values[0]} ({df[df['id']==x]['vehicle_type'].values[0]})"
                    )
                    if st.form_submit_button("Delete Selected Vehicle", type="secondary"):
                        result, error = delete_vehicle(vehicle_to_delete)
                        if error:
                            st.error(error)
                        else:
                            st.success("Vehicle deleted successfully!")
                            st.rerun()
        else:
            st.info("No vehicles registered yet")
    
    # Tab 3: My Bookings
    with tabs[2]:
        st.subheader("📅 My Bookings")
        
        with st.expander("➕ Book a Parking Slot", expanded=False):
            if vehicles:
                with st.form("book_vehicle_form"):
                    vehicle_options = {v['id']: f"{v['vehicle_number']} ({v['vehicle_type']})" for v in vehicles}
                    selected_vehicle = st.selectbox(
                        "Select Vehicle",
                        options=list(vehicle_options.keys()),
                        format_func=lambda x: vehicle_options[x]
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        entry_date = st.date_input("Expected Entry Date", datetime.now())
                    with col2:
                        entry_time = st.time_input("Expected Entry Time", datetime.now().time())
                    
                    if st.form_submit_button("Book Now", use_container_width=True, type="primary"):
                        expected_datetime = datetime.combine(entry_date, entry_time)
                        result, error = book_vehicle(selected_vehicle, expected_datetime)
                        if error:
                            st.error(error)
                        else:
                            st.success(f"Booking #{result.get('booking_id')} created successfully!")
                            
                            if result.get('qr_code_path'):
                                st.image(f"http://localhost:8000/{result['qr_code_path']}", width=200)
                            st.rerun()
            else:
                st.warning("Please register a vehicle first")
        
        # Display bookings
        if bookings:
            # Create a vehicle lookup dictionary for faster access
            vehicle_lookup = {}
            if vehicles:
                for v in vehicles:
                    vehicle_lookup[v['id']] = v
            
            for booking in bookings:
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
                    
                    with col1:
                        st.write(f"**Booking #{booking['id']}**")
                    
                    with col2:
                        # Safely get vehicle information
                        vehicle_number = "Unknown Vehicle"
                        if booking['vehicle_id'] in vehicle_lookup:
                            vehicle_number = vehicle_lookup[booking['vehicle_id']]['vehicle_number']
                        else:
                            # Try to fetch vehicle info if not in lookup
                            all_vehicles, _ = get_all_vehicles()
                            for v in (all_vehicles or []):
                                if v['id'] == booking['vehicle_id']:
                                    vehicle_number = v['vehicle_number']
                                    vehicle_lookup[booking['vehicle_id']] = v
                                    break
                        st.write(vehicle_number)
                    
                    with col3:
                        # Determine correct status
                        is_active = booking.get('is_active', False)
                        is_used = booking.get('is_used', False)
                        
                        if is_active and not is_used:
                            status = "✅ Active"
                            status_color = "green"
                        elif is_used:
                            status = "✅ Used"
                            status_color = "blue"
                        else:
                            status = "❌ Cancelled"
                            status_color = "red"
                        
                        st.markdown(f"<span style='color:{status_color}'>{status}</span>", unsafe_allow_html=True)
                    
                    with col4:
                        if booking.get('qr_image_path') and booking.get('is_active'):
                            qr_key = f"show_qr_{booking['id']}"
                            if qr_key not in st.session_state:
                                st.session_state[qr_key] = False
                            
                            if st.button(f"👁️ Show QR", key=f"qr_btn_{booking['id']}"):
                                st.session_state[qr_key] = True
                                st.rerun()
                    
                    # Show QR code below the row if button was clicked
                    qr_key = f"show_qr_{booking['id']}"
                    if st.session_state.get(qr_key, False):
                        st.image(f"http://localhost:8000/{booking['qr_image_path']}", width=200)
                        if st.button(f"Close QR", key=f"close_qr_{booking['id']}"):
                            st.session_state[qr_key] = False
                            st.rerun()
                    
                    with col5:
                        if booking.get('is_active'):
                            if st.button(f"❌ Cancel", key=f"cancel_{booking['id']}"):
                                result, error = cancel_booking(booking['id'])
                                if error:
                                    st.error(error)
                                else:
                                    st.success("Booking cancelled!")
                                    st.rerun()
                    
                    st.divider()
        else:
            st.info("No bookings yet")
    
    # Tab 4: Profile
    with tabs[3]:
        st.subheader("👤 My Profile")
        
        if profile:
            with st.form("update_profile_form"):
                new_username = st.text_input("Username", value=profile.get('username', ''))
                new_email = st.text_input("Email", value=profile.get('email', ''))
                new_phone = st.text_input("Phone", value=profile.get('phone', ''))
                new_password = st.text_input("New Password (leave blank to keep current)", type="password")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Update Profile", use_container_width=True, type="primary"):
                        result, error = update_user_profile(new_username, new_email, new_phone, new_password or None)
                        if error:
                            st.error(error)
                        else:
                            st.success("Profile updated successfully!")
                            st.rerun()
                with col2:
                    if st.form_submit_button("Cancel", use_container_width=True):
                        st.rerun()
            
            st.markdown("---")
            if st.button("Delete My Account", type="secondary"):
                st.warning("This action cannot be undone. Please contact admin to delete your account.")
        else:
            st.error("Could not load profile")
            
    
    # Tab 5: Wallet
    with tabs[4]:
        st.subheader("💰 Wallet Management")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Current Balance", f"₹{wallet_balance:.2f}")
        
        with col2:
            with st.form("topup_form"):
                amount = st.number_input("Amount to Add (₹)", min_value=10.0, max_value=10000.0, step=50.0, value=100.0)
                if st.form_submit_button("Add Money to Wallet", use_container_width=True, type="primary"):
                    result, error = topup_user_wallet(amount)
                    if error:
                        st.error(error)
                    else:
                        st.success(f"₹{amount:.2f} added to wallet! New balance: ₹{result.get('wallet_balance', 0):.2f}")
                        time_module.sleep(1)
                        st.rerun()
        
        st.markdown("---")
        st.subheader("Recent Transactions")
        st.info("Transaction history will be displayed here")

    with tabs[5]:  
        st.subheader("📊 My Parking History")
        
        # Refresh button
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        
        # Fetch user's parking history
        history_data, error = get_my_parking_history()
        
        if error:
            st.error(f"Failed to load history: {error}")
        elif history_data:
            if len(history_data) > 0:
                # Convert to DataFrame
                df = pd.DataFrame(history_data)
                
                # Debug info (remove after testing)
                with st.expander("Debug Info", expanded=False):
                    st.write("Columns:", df.columns.tolist())
                    st.write("First row:", df.iloc[0].to_dict() if not df.empty else "Empty")
                
                # Format datetime columns
                for col in ['entry_time', 'exit_time']:
                    if col in df.columns:
                        try:
                            df[col] = pd.to_datetime(df[col]).dt.strftime('%Y-%m-%d %H:%M')
                        except:
                            df[col] = str(df[col])
                
                # Calculate statistics
                total_sessions = len(df)
                total_spent = df['parking_fee'].sum() if 'parking_fee' in df.columns else 0
                avg_fee = total_spent / total_sessions if total_sessions > 0 else 0
                
                # Display metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Sessions", total_sessions)
                with col2:
                    st.metric("Total Spent", f"₹{total_spent:.2f}")
                with col3:
                    st.metric("Average per Visit", f"₹{avg_fee:.2f}")
                with col4:
                    # Most used vehicle type
                    if 'vehicle_type' in df.columns:
                        most_used = df['vehicle_type'].mode()[0] if not df['vehicle_type'].empty else "N/A"
                        st.metric("Most Used", most_used)
                
                st.markdown("---")
                
                # Filters
                with st.expander("🔍 Filter History", expanded=False):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        # Filter by vehicle type
                        if 'vehicle_type' in df.columns:
                            vehicle_types = ['All'] + sorted(df['vehicle_type'].unique().tolist())
                            filter_type = st.selectbox("Vehicle Type", vehicle_types, key="user_history_type")
                        else:
                            filter_type = 'All'
                    
                    with col2:
                        # Filter by vehicle number
                        if 'vehicle_number' in df.columns:
                            vehicles = ['All'] + sorted(df['vehicle_number'].unique().tolist())
                            filter_vehicle = st.selectbox("Vehicle Number", vehicles, key="user_history_vehicle")
                        else:
                            filter_vehicle = 'All'
                    
                    with col3:
                        # Date range filter
                        date_range = st.selectbox(
                            "Time Period",
                            ["All Time", "Last 7 Days", "Last 30 Days", "This Month", "Last Month"],
                            key="user_history_date"
                        )
                
                # Prepare display dataframe
                display_columns = []
                column_mapping = {
                    'vehicle_number': 'Vehicle',
                    'vehicle_type': 'Type',
                    'entry_time': 'Entry Time',
                    'exit_time': 'Exit Time',
                    'parking_fee': 'Fee (₹)',
                    'slot_number': 'Slot'
                }
                
                # Only include columns that exist
                for col, display_name in column_mapping.items():
                    if col in df.columns:
                        display_columns.append(col)
                
                if display_columns:
                    display_df = df[display_columns].copy()
                    display_df.columns = [column_mapping[col] for col in display_columns]
                    
                    # Apply filters
                    filtered_df = display_df.copy()
                    
                    # Vehicle type filter
                    if filter_type != 'All' and 'Type' in filtered_df.columns:
                        filtered_df = filtered_df[filtered_df['Type'] == filter_type]
                    
                    # Vehicle number filter
                    if filter_vehicle != 'All' and 'Vehicle' in filtered_df.columns:
                        filtered_df = filtered_df[filtered_df['Vehicle'] == filter_vehicle]
                    
                    # Date filter
                    if date_range != 'All Time' and 'Entry Time' in filtered_df.columns:
                        try:
                            filtered_df['temp_date'] = pd.to_datetime(filtered_df['Entry Time'])
                            today = datetime.now().date()
                            
                            if date_range == 'Last 7 Days':
                                week_ago = today - timedelta(days=7)
                                filtered_df = filtered_df[filtered_df['temp_date'].dt.date >= week_ago]
                            elif date_range == 'Last 30 Days':
                                month_ago = today - timedelta(days=30)
                                filtered_df = filtered_df[filtered_df['temp_date'].dt.date >= month_ago]
                            elif date_range == 'This Month':
                                filtered_df = filtered_df[filtered_df['temp_date'].dt.month == today.month]
                            elif date_range == 'Last Month':
                                last_month = today.month - 1 if today.month > 1 else 12
                                last_month_year = today.year if today.month > 1 else today.year - 1
                                filtered_df = filtered_df[
                                    (filtered_df['temp_date'].dt.month == last_month) & 
                                    (filtered_df['temp_date'].dt.year == last_month_year)
                                ]
                            
                            filtered_df = filtered_df.drop(columns=['temp_date'])
                        except Exception as e:
                            st.warning(f"Date filter error: {e}")
                    
                    # Show record count
                    st.caption(f"Showing {len(filtered_df)} of {len(display_df)} records")
                    
                    # Display the dataframe
                    st.dataframe(
                        filtered_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Fee (₹)": st.column_config.NumberColumn(
                                "Fee (₹)",
                                format="₹%.2f"
                            )
                        } if 'Fee (₹)' in filtered_df.columns else {}
                    )
                    
                    # Download button for user's history
                    if not filtered_df.empty:
                        csv = filtered_df.to_csv(index=False)
                        st.download_button(
                            label="📥 Download My History",
                            data=csv,
                            file_name=f"my_parking_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                        )
                    
                    # Additional statistics
                    with st.expander("📊 More Statistics", expanded=False):
                        if 'Fee (₹)' in filtered_df.columns and not filtered_df.empty:
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.subheader("Monthly Spending")
                                # Create a copy with date for monthly grouping
                                monthly_df = df.copy()
                                monthly_df['month'] = pd.to_datetime(monthly_df['entry_time']).dt.strftime('%Y-%m')
                                monthly_spending = monthly_df.groupby('month')['parking_fee'].sum().reset_index()
                                monthly_spending.columns = ['Month', 'Spent (₹)']
                                st.dataframe(monthly_spending, use_container_width=True, hide_index=True)
                            
                            with col2:
                                st.subheader("Vehicle Usage")
                                if 'vehicle_type' in df.columns and 'parking_fee' in df.columns:
                                    vehicle_stats = df.groupby('vehicle_type').agg({
                                        'parking_fee': ['count', 'sum']
                                    }).round(2)
                                    vehicle_stats.columns = ['Sessions', 'Total Spent']
                                    st.dataframe(vehicle_stats, use_container_width=True)
                else:
                    st.warning("No displayable data")
            else:
                st.info("📭 You haven't used the parking service yet. Your history will appear here after your first parking session.")
        else:
            st.info("No parking history available")
    

def admin_dashboard():
    """Admin dashboard with nested navigation"""
    st.title(f"👑 Admin Dashboard - {st.session_state.user_info.get('username', 'Admin')}")
    
    # Auto-refresh every 15 seconds
    if time_module.time() - st.session_state.last_refresh > 15:
        refresh_parking_data()
    
    # Get dashboard stats
    stats, stats_error = get_admin_dashboard()
    wallet_data, wallet_error = get_admin_wallet_balance()
    
    admin_wallet_balance = wallet_data.get('wallet_balance', 0) if wallet_data else 0
    
    # Nested navigation
    main_nav = st.sidebar.radio(
        "Admin Navigation",
        ["📊 Overview", "🅿️ Parking Management", "👥 User Management", "📋 Booking Management", "🚗 Vehicle Management", "⚙️ Settings", "💰 Wallet", "📊 History"]
    )
    
    if main_nav == "📊 Overview":
        st.subheader("📊 System Overview")
        
        if stats:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Users", stats.get('total_users', 0))
                st.metric("Total Past Users", stats.get('total_users_who_has_used_parking', 0))
                st.metric("Total Vehicles", stats.get('total_vehicles_registered', 0))
                st.metric("Total Bookings", stats.get('total_bookings', 0))
            
            with col2:
                st.metric("Total Slots", stats.get('total_slots', 0))
                st.metric("Occupied", stats.get('occupied_slots', 0))
                st.metric("Available", stats.get('available_slots', 0))
                st.metric("Total Revenue", f"₹{stats.get('total_revenue', 0):.2f}")
    
    elif main_nav == "🅿️ Parking Management":
        st.subheader("🅿️ Parking Management")
        
        # Nested tabs for parking management
        parking_tab = st.radio(
            "Parking Management",
            ["🗺️ View Grid", "➕ Add Spots", "➖ Remove Slots", "✏️ Update Slot", "🗑️ Delete Slots"],
            horizontal=True
        )
        
        if parking_tab == "🗺️ View Grid":
            slots, error = refresh_parking_data()
            if slots:
                display_parking_grid(slots)
        
        elif parking_tab == "➕ Add Spots":
            with st.form("add_slots_form"):
                col1, col2 = st.columns(2)
                with col1:
                    vehicle_type = st.selectbox("Vehicle Type", ["Two_Wheeler", "Four_Wheeler"])
                    zone = st.text_input("Zone", value="A").upper()
                with col2:
                    count = st.number_input("Number of Spots", min_value=1, max_value=100, value=5)
                
                if st.form_submit_button("Add Spots", use_container_width=True, type="primary"):
                    result, error = add_parking_spots(vehicle_type, count, zone)
                    if error:
                        st.error(error)
                    else:
                        st.success(result.get('message', 'Spots added successfully'))
                        refresh_parking_data()
                        st.rerun()
        
        elif parking_tab == "➖ Remove Slots":
            with st.form("remove_slots_form"):
                col1, col2 = st.columns(2)
                with col1:
                    vehicle_type_r = st.selectbox("Vehicle Type", ["Two_Wheeler", "Four_Wheeler"], key="remove_type")
                    zone_r = st.text_input("Zone", value="EARLY").upper()
                with col2:
                    start_number = st.number_input("Start Number", min_value=1, value=400, step=1)
                    count_r = st.number_input("Number of Spots", min_value=1, value=100, step=1)
                
                submitted = st.form_submit_button("Remove Slots", use_container_width=True, type="secondary")
                
                if submitted:
                    remove_data = {
                        "vehicle_type": vehicle_type_r,
                        "start_number": start_number,
                        "count": count_r,
                        "zone": zone_r
                    }
                    
                    result, error = remove_parking_spots(remove_data)
                    if error:
                        st.error(f"Error: {error}")
                    else:
                        st.success(result.get('message', 'Spots removed successfully'))
                        refresh_parking_data()
                        st.rerun()
        
        elif parking_tab == "✏️ Update Slot":
            slots, error = get_all_parking_slots()
            if slots:
                df = pd.DataFrame(slots)
                if not df.empty:
                    with st.form("update_slot_form"):
                        # Select slot to update
                        slot_options = {row['id']: f"{row['slot_number']} (Zone: {row['zone']}, Type: {row['vehicle_type']})" 
                                       for _, row in df.iterrows()}
                        selected_slot_id = st.selectbox(
                            "Select Slot to Update",
                            options=list(slot_options.keys()),
                            format_func=lambda x: slot_options[x]
                        )
                        
                        # Get current slot data
                        selected_slot = df[df['id'] == selected_slot_id].iloc[0]
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            new_slot_number = st.text_input("Slot Number", value=selected_slot['slot_number'])
                            new_vehicle_type = st.selectbox(
                                "Vehicle Type",
                                ["Two_Wheeler", "Four_Wheeler"],
                                index=0 if selected_slot['vehicle_type'] == "Two_Wheeler" else 1
                            )
                        with col2:
                            new_zone = st.text_input("Zone", value=selected_slot['zone']).upper()
                            new_is_active = st.checkbox("Is Active", value=selected_slot['is_active'])
                        
                        st.info("Note: Occupancy status is automatically managed by the system")
                        
                        if st.form_submit_button("Update Slot", use_container_width=True, type="primary"):
                            # Prepare update data
                            update_data = {
                                "slot_number": new_slot_number if new_slot_number != selected_slot['slot_number'] else None,
                                "vehicle_type": new_vehicle_type if new_vehicle_type != selected_slot['vehicle_type'] else None,
                                "zone": new_zone if new_zone != selected_slot['zone'] else None,
                                "is_active": new_is_active if new_is_active != selected_slot['is_active'] else None
                            }
                            # Remove None values
                            update_data = {k: v for k, v in update_data.items() if v is not None}
                            
                            if update_data:
                                result, error = update_parking_slot(selected_slot_id, update_data)
                                if error:
                                    st.error(error)
                                else:
                                    st.success("Slot updated successfully!")
                                    refresh_parking_data()
                                    st.rerun()
                            else:
                                st.info("No changes to update")
        
        elif parking_tab == "🗑️ Delete Slots":
            slots, error = get_all_parking_slots()
            if slots:
                df = pd.DataFrame(slots)
                if not df.empty:
                    with st.form("delete_slot_form"):
                        slot_to_delete = st.selectbox(
                            "Select slot to delete",
                            options=df['id'].tolist(),
                            format_func=lambda x: f"{df[df['id']==x]['slot_number'].values[0]} (Zone {df[df['id']==x]['zone'].values[0]})"
                        )
                        
                        is_occupied = df[df['id'] == slot_to_delete]['is_occupied'].values[0] if len(df[df['id'] == slot_to_delete]) > 0 else False
                        
                        if is_occupied:
                            st.warning("⚠️ This slot is currently occupied and cannot be deleted")
                        
                        if st.form_submit_button("Delete Selected Slot", disabled=is_occupied, type="secondary"):
                            result, error = delete_parking_slot(slot_to_delete)
                            if error:
                                st.error(error)
                            else:
                                st.success("Slot deleted successfully!")
                                refresh_parking_data()
                                st.rerun()
    
    elif main_nav == "👥 User Management":
        st.subheader("👥 User Management")
        
        users, users_error = get_all_users()
        if users:
            df = pd.DataFrame(users)
            if not df.empty:
                if 'password_hash' in df.columns:
                    df = df.drop(columns=['password_hash'])
                
                display_df = df[['id', 'username', 'email', 'phone', 'role', 'created_at']].copy()
                display_df.columns = ['ID', 'Username', 'Email', 'Phone', 'Role', 'Joined']
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                with st.form("delete_user_form"):
                    user_to_delete = st.selectbox(
                        "Select user to delete",
                        options=df['id'].tolist(),
                        format_func=lambda x: f"{df[df['id']==x]['username'].values[0]} ({df[df['id']==x]['email'].values[0]})"
                    )
                    
                    if st.form_submit_button("Delete Selected User", type="secondary"):
                        result, error = delete_user(user_to_delete)
                        if error:
                            st.error(error)
                        else:
                            st.success("User deleted successfully!")
                            st.rerun()
    
    elif main_nav == "📋 Booking Management":
        st.subheader("📋 Booking Management")
        
        bookings, bookings_error = get_all_bookings()
        if bookings:
            df = pd.DataFrame(bookings)
            if not df.empty:
                display_df = df[['id', 'user_id', 'vehicle_id', 'expected_entry_time', 'is_active', 'is_used', 'booking_time']].copy()
                display_df.columns = ['ID', 'User ID', 'Vehicle ID', 'Expected Entry', 'Active', 'Used', 'Booked On']
                
                for col in ['Expected Entry', 'Booked On']:
                    if col in display_df.columns:
                        display_df[col] = pd.to_datetime(display_df[col]).dt.strftime('%Y-%m-%d %H:%M')
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                with st.form("delete_booking_form"):
                    booking_to_delete = st.selectbox(
                        "Select booking to delete",
                        options=df['id'].tolist(),
                        format_func=lambda x: f"Booking #{x}"
                    )
                    
                    if st.form_submit_button("Delete Selected Booking", type="secondary"):
                        result, error = delete_booking(booking_to_delete)
                        if error:
                            st.error(error)
                        else:
                            st.success("Booking deleted successfully!")
                            st.rerun()
    
    elif main_nav == "🚗 Vehicle Management":
        st.subheader("🚗 Vehicle Management")
        
        vehicles, vehicles_error = get_all_vehicles()
        if vehicles:
            df = pd.DataFrame(vehicles)
            if not df.empty:
                display_df = df[['id', 'user_id', 'vehicle_number', 'vehicle_type', 'created_at']].copy()
                display_df.columns = ['ID', 'User ID', 'Vehicle Number', 'Type', 'Registered On']
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                with st.form("delete_vehicle_admin_form"):
                    vehicle_to_delete = st.selectbox(
                        "Select vehicle to delete",
                        options=df['id'].tolist(),
                        format_func=lambda x: f"{df[df['id']==x]['vehicle_number'].values[0]}"
                    )
                    
                    if st.form_submit_button("Delete Selected Vehicle", type="secondary"):
                        result, error = delete_vehicle_admin(vehicle_to_delete)
                        if error:
                            st.error(error)
                        else:
                            st.success("Vehicle deleted successfully!")
                            st.rerun()
    
    elif main_nav == "⚙️ Settings":
        st.subheader("⚙️ System Settings")
        
        with st.form("settings_form"):
            col1, col2 = st.columns(2)
            with col1:
                start_time = st.time_input("Start Time")
                end_time = st.time_input("End Time")
                default_zone = st.text_input("Default Zone")
                default_zone_size = st.number_input("Default Zone Size")
            
            with col2:
                main_zone = st.text_input("Main Zone")
                per_minute_fee = st.number_input("Per Minute Fee (₹)")
                grace_period = st.number_input("Grace Period (minutes)")
                penalty_per_minute = st.number_input("Penalty Per Minute (₹)")
            
            if st.form_submit_button("Save Settings", use_container_width=True, type="primary"):
                settings = {
                    "start_time": start_time.strftime("%H:%M"),
                    "end_time": end_time.strftime("%H:%M"),
                    "default_zone": default_zone,
                    "default_zone_size": int(default_zone_size),
                    "main_zone": main_zone,
                    "per_minute_fee": float(per_minute_fee),
                    "overdue_grace_period_minutes": int(grace_period),
                    "overdue_penalty_per_minute": float(penalty_per_minute)
                }
                result, error = change_default_values(settings)
                if error:
                    st.error(error)
                else:
                    st.success("Settings updated successfully!")
    
    elif main_nav == "💰 Wallet":
        st.subheader("💰 Admin Wallet")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Current Balance", f"₹{admin_wallet_balance:.2f}")
        
        with col2:
            with st.form("admin_topup_form"):
                amount = st.number_input("Amount to Add (₹)", min_value=10.0, max_value=100000.0, step=100.0, value=1000.0)
                if st.form_submit_button("Add Money to Admin Wallet", use_container_width=True, type="primary"):
                    result, error = topup_admin_wallet(amount)
                    if error:
                        st.error(error)
                    else:
                        st.success(f"₹{amount:.2f} added to admin wallet! New balance: ₹{result.get('wallet_balance', 0):.2f}")
                        time_module.sleep(1)
                        st.rerun()

    elif main_nav == "📜 Parking History":
        st.subheader("📜 Parking History")
        
        # Add refresh button
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        
        # Fetch history data
        history_data, error = get_parking_history()
        
        if error:
            st.error(f"Failed to load parking history: {error}")
        elif history_data is not None:
            # Check if we have data
            if len(history_data) > 0:
                # Convert to DataFrame
                df = pd.DataFrame(history_data)
                
                # Debug: Show raw data structure (remove after fixing)
                with st.expander("Debug Info", expanded=False):
                    st.write("Data Types:", df.dtypes)
                    st.write("Column Names:", df.columns.tolist())
                    st.write("First Row:", df.iloc[0].to_dict() if not df.empty else "No data")
                
                # Format datetime columns safely
                for col in ['entry_time', 'exit_time']:
                    if col in df.columns:
                        try:
                            df[col] = pd.to_datetime(df[col]).dt.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            df[col] = str(df[col])  # Convert to string if datetime conversion fails
                
                # Display metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Parking Sessions", len(df))
                
                # Calculate total fees safely
                if 'parking_fee' in df.columns:
                    total_fees = df['parking_fee'].sum() if not df['parking_fee'].isna().all() else 0
                    with col2:
                        st.metric("Total Revenue", f"₹{total_fees:.2f}")
                    with col3:
                        avg_fee = total_fees / len(df) if len(df) > 0 else 0
                        st.metric("Average Fee per Session", f"₹{avg_fee:.2f}")
                else:
                    with col2:
                        st.metric("Total Revenue", "N/A")
                    with col3:
                        st.metric("Average Fee", "N/A")
                
                st.markdown("---")
                
                # Prepare display dataframe
                display_columns = []
                column_mapping = {
                    'id': 'ID',
                    'user_id': 'User ID',
                    'vehicle_number': 'Vehicle Number',
                    'vehicle_type': 'Vehicle Type',
                    'entry_time': 'Entry Time',
                    'exit_time': 'Exit Time',
                    'parking_fee': 'Fee (₹)',
                    'slot_number': 'Slot'
                }
                
                # Only include columns that exist
                for col, display_name in column_mapping.items():
                    if col in df.columns:
                        display_columns.append(col)
                
                if display_columns:
                    display_df = df[display_columns].copy()
                    display_df.columns = [column_mapping[col] for col in display_columns]
                    
                    # Format fee column if it exists
                    if 'Fee (₹)' in display_df.columns:
                        # Ensure fee is numeric
                        display_df['Fee (₹)'] = pd.to_numeric(display_df['Fee (₹)'], errors='coerce').fillna(0)
                    
                    # Add filters
                    with st.expander("🔍 Filter History", expanded=False):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Filter by vehicle type
                            if 'Vehicle Type' in display_df.columns:
                                vehicle_types = ['All'] + sorted(display_df['Vehicle Type'].unique().tolist())
                                filter_vehicle_type = st.selectbox("Vehicle Type", vehicle_types)
                            else:
                                filter_vehicle_type = 'All'
                        
                        with col2:
                            # Filter by date range
                            date_range = st.selectbox(
                                "Date Range",
                                ["All Time", "Today", "Last 7 Days", "Last 30 Days"]
                            )
                    
                    # Apply filters
                    filtered_df = display_df.copy()
                    
                    # Vehicle type filter
                    if filter_vehicle_type != 'All' and 'Vehicle Type' in filtered_df.columns:
                        filtered_df = filtered_df[filtered_df['Vehicle Type'] == filter_vehicle_type]
                    
                    # Date filter
                    if date_range != 'All Time' and 'Entry Time' in filtered_df.columns:
                        try:
                            filtered_df['temp_date'] = pd.to_datetime(filtered_df['Entry Time'])
                            today = datetime.now().date()
                            
                            if date_range == 'Today':
                                filtered_df = filtered_df[filtered_df['temp_date'].dt.date == today]
                            elif date_range == 'Last 7 Days':
                                week_ago = today - timedelta(days=7)
                                filtered_df = filtered_df[filtered_df['temp_date'].dt.date >= week_ago]
                            elif date_range == 'Last 30 Days':
                                month_ago = today - timedelta(days=30)
                                filtered_df = filtered_df[filtered_df['temp_date'].dt.date >= month_ago]
                            
                            filtered_df = filtered_df.drop(columns=['temp_date'])
                        except Exception as e:
                            st.warning(f"Date filtering error: {e}")
                    
                    # Display count
                    st.write(f"Showing {len(filtered_df)} records")
                    
                    # Display the dataframe
                    st.dataframe(
                        filtered_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Fee (₹)": st.column_config.NumberColumn(
                                "Fee (₹)",
                                format="₹%.2f"
                            )
                        } if 'Fee (₹)' in filtered_df.columns else {}
                    )
                    
                    # Download button
                    if not filtered_df.empty:
                        csv = filtered_df.to_csv(index=False)
                        st.download_button(
                            label="📥 Download as CSV",
                            data=csv,
                            file_name=f"parking_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                        )
                        
                        # Show summary statistics
                        with st.expander("📊 Summary Statistics", expanded=False):
                            if 'Fee (₹)' in filtered_df.columns:
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Sessions", len(filtered_df))
                                with col2:
                                    st.metric("Total Revenue", f"₹{filtered_df['Fee (₹)'].sum():.2f}")
                                with col3:
                                    st.metric("Average Fee", f"₹{filtered_df['Fee (₹)'].mean():.2f}")
                                with col4:
                                    st.metric("Max Fee", f"₹{filtered_df['Fee (₹)'].max():.2f}")
                                
                                # Vehicle type breakdown
                                if 'Vehicle Type' in filtered_df.columns:
                                    st.subheader("Vehicle Type Breakdown")
                                    type_stats = filtered_df.groupby('Vehicle Type').agg({
                                        'Fee (₹)': ['count', 'sum', 'mean']
                                    }).round(2)
                                    type_stats.columns = ['Sessions', 'Total Revenue', 'Avg Fee']
                                    st.dataframe(type_stats, use_container_width=True)
                else:
                    st.warning("No displayable columns found in the data")
            else:
                st.info("📭 No parking history records found. History will appear here when vehicles exit the parking.")
        else:
            st.info("No parking history data available")
        

def main():
    """Main app function"""
    st.set_page_config(
        page_title="Smart Parking System",
        page_icon="🅿️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    init_session_state()
    
    with st.sidebar:
        if st.session_state.authenticated:
            try:
                st.image("SPARK.png", width=80)
            except:
                st.markdown("# 🅿️")
            
            st.title(f"Welcome, {st.session_state.user_info.get('username', 'User')}")
            st.markdown(f"**Role:** {st.session_state.role.upper()}")
            st.markdown("---")
            
            if st.button("🏠 Dashboard", use_container_width=True):
                st.session_state.page = "Dashboard"
                st.rerun()
            
            if st.button("🚪 Logout", use_container_width=True, type="primary"):
                logout()
    
    if not st.session_state.authenticated:
        if st.session_state.page == "Register":
            register_page()
        else:
            login_page()
    else:
        if st.session_state.role == "admin":
            admin_dashboard()
        else:
            user_dashboard()

if __name__ == "__main__":
    main()