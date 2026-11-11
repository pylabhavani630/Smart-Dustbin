import streamlit as st
import pandas as pd
import sqlite3, hashlib, json, os, re
from datetime import datetime
from PIL import Image, ExifTags
from io import BytesIO
from pathlib import Path

DB = os.path.join(os.path.dirname(__file__), 'waste_management.db')
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

st.set_page_config(page_title='Smart Waste Management', page_icon='♻️', layout='wide')
st.markdown('''<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"]{font-family:Inter,sans-serif}.stApp{background:#07152d;color:#eef5ff}
[data-testid="stSidebar"]{background:#102b50} [data-testid="stSidebar"] *{color:#eef5ff!important}
.block-container{
    padding-top:1.2rem;
    max-width:1500px;
}

/* Main dashboard text */
h1,h2,h3{
    color:#eef5ff !important;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stWidgetLabel"] p{
    color:#eef5ff;
}

/* Streamlit information messages */
div[data-testid="stAlert"]{
    background:#10284b !important;
    border:1px solid #31577f !important;
    border-radius:12px !important;
}

div[data-testid="stAlert"] p,
div[data-testid="stAlert"] span,
div[data-testid="stAlert"] div{
    color:#eef5ff !important;
    -webkit-text-fill-color:#eef5ff !important;
}
.panel{background:#10284b;border:1px solid #25466f;border-radius:13px;padding:15px;margin-bottom:12px}
.small{color:#a9bdd8;font-size:13px}.stButton button{border-radius:9px;font-weight:700}
/* White form fields: use red text for clear readability */
.stTextInput input,.stTextArea textarea,.stNumberInput input,
[data-baseweb="input"] input,[data-baseweb="textarea"] textarea,
[data-baseweb="select"] [role="combobox"],
[data-baseweb="datepicker"] input,
[data-testid="stDateInput"] input,
[data-testid="stTimeInput"] input {
    color:#d00000 !important;
    -webkit-text-fill-color:#d00000 !important;
    background-color:#ffffff !important;
}
.stTextInput input::placeholder,.stTextArea textarea::placeholder,
.stNumberInput input::placeholder,[data-baseweb="input"] input::placeholder,
[data-baseweb="textarea"] textarea::placeholder {
    color:#c44 !important;
    -webkit-text-fill-color:#c44 !important;
    opacity:1 !important;
}

[data-baseweb="select"] [role="combobox"] * {color:#d00000 !important;}
[data-baseweb="popover"] [role="option"] {color:#d00000 !important;}
/* Keep text red in Streamlit's other light/white input surfaces too. */
[data-testid="stDateInput"] *,[data-testid="stTimeInput"] *,
[data-testid="stNumberInput"] input,[data-testid="stFileUploader"] section,
[data-testid="stFileUploader"] section *,
[data-baseweb="select"] [role="combobox"],
[data-baseweb="select"] [role="combobox"] *,
[data-baseweb="popover"] *,[role="listbox"] *,[role="option"] {
    color:#d00000 !important;
    -webkit-text-fill-color:#d00000 !important;
}
/* Dropdown/menu items stay readable even when Streamlit opens them in a white panel. */
[data-baseweb="menu"] *,[data-baseweb="menu"] [role="option"] {
    color:#d00000 !important;
    -webkit-text-fill-color:#d00000 !important;
}
.stButton button,.stDownloadButton button,.stFormSubmitButton button {
    color:#d00000 !important;
    -webkit-text-fill-color:#d00000 !important;
}
</style>''', unsafe_allow_html=True)
st.markdown("""
<style>

/* Demo Credentials - Readable Red Text */
div[data-testid="stCode"] {
    background-color: #FFFFFF !important;
    border: 2px solid #DC3545 !important;
    border-radius: 12px !important;
}

div[data-testid="stCode"] pre,
div[data-testid="stCode"] code {
    color: #D00000 !important;
    -webkit-text-fill-color: #D00000 !important;
    opacity: 1 !important;
    font-weight: 700 !important;
}

/* Copy Button */
div[data-testid="stCode"] button {
    color: #D00000 !important;
}

</style>
""", unsafe_allow_html=True)

# ---------------- Database ----------------
def db():
    c=sqlite3.connect(DB, check_same_thread=False)
    c.row_factory=sqlite3.Row
    return c

def init_db():
    c=db(); q=c.cursor()
    q.executescript('''
    CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY,password TEXT,role TEXT,name TEXT,phone TEXT);
    CREATE TABLE IF NOT EXISTS complaints(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT,description TEXT,photo TEXT,photo_hash TEXT,verification TEXT,latitude REAL,longitude REAL,address TEXT,status TEXT,created_at TEXT,assigned_truck TEXT,assigned_driver TEXT,completed_at TEXT);
    CREATE TABLE IF NOT EXISTS workers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,phone TEXT,role TEXT,shift TEXT,status TEXT);
    CREATE TABLE IF NOT EXISTS trucks(id INTEGER PRIMARY KEY AUTOINCREMENT,truck_no TEXT UNIQUE,driver TEXT,phone TEXT,status TEXT,current_lat REAL,current_lon REAL,current_area TEXT);
    CREATE TABLE IF NOT EXISTS dustbins(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,area TEXT,latitude REAL,longitude REAL,status TEXT,created_at TEXT);
    ''')
    defaults=[('user','user123','User','Demo Citizen','9000000001'),('municipal','muni123','Municipality','Municipal Officer','9000000002'),('admin','admin123','Admin','System Admin','9000000003')]
    for x in defaults:q.execute('INSERT OR IGNORE INTO users VALUES(?,?,?,?,?)',x)
    if q.execute('SELECT COUNT(*) FROM workers').fetchone()[0]==0:
        q.executemany('INSERT INTO workers(name,phone,role,shift,status) VALUES(?,?,?,?,?)',[
            ('Ravi Kumar','9000000011','Sanitation Worker','Morning','Active'),('Suresh','9000000012','Driver','Morning','Active'),('Lakshmi','9000000013','Supervisor','Day','Active')])
    if q.execute('SELECT COUNT(*) FROM trucks').fetchone()[0]==0:
        q.executemany('INSERT INTO trucks(truck_no,driver,phone,status,current_area) VALUES(?,?,?,?,?)',[
            ('AP-01-WM-101','Suresh','9000000012','Available','Municipal Depot'),('AP-01-WM-102','Ramesh','9000000014','On Route','Market Road'),('AP-01-WM-103','Kiran','9000000015','Maintenance','Workshop')])
    c.commit();c.close()
init_db()

def rows(sql,args=()):
    c=db(); out=pd.read_sql_query(sql,c,params=args);c.close();return out

def run(sql,args=()):
    c=db();c.execute(sql,args);c.commit();c.close()

def digest(data):return hashlib.sha256(data).hexdigest()

def perceptual_hash(data):
    """Small difference-hash used to flag visually similar uploads for human review."""
    try:
        im=Image.open(BytesIO(data)).convert('L').resize((9, 8))
        px=list(im.getdata())
        bits=[]
        for y in range(8):
            for x in range(8):
                bits.append(1 if px[y*9+x] > px[y*9+x+1] else 0)
        return ''.join(str(v) for v in bits)
    except Exception:
        return ''

def similar_photo_exists(data):
    new_hash=perceptual_hash(data)
    if not new_hash:
        return False
    existing=rows('SELECT id,photo FROM complaints')
    for _, item in existing.iterrows():
        old_path=os.path.join(os.path.dirname(__file__), str(item.photo or ''))
        if not os.path.isfile(old_path):
            continue
        try:
            old_hash=perceptual_hash(Path(old_path).read_bytes())
            if not old_hash or len(old_hash) != len(new_hash):
                continue
            distance=sum(a != b for a,b in zip(new_hash, old_hash))
            if distance <= 5:
                return True
        except Exception:
            continue
    return False

def image_screening(data):
    """Basic integrity screening only; cannot prove whether an image is AI-generated or genuine."""
    try:
        im=Image.open(BytesIO(data)); w,h=im.size
        exif=im.getexif(); has_camera=bool(exif)
        if w<200 or h<200:return 'Review Required – low resolution', 'Image resolution is unusually low.'
        if has_camera:return 'Metadata Found – Review', 'EXIF metadata exists; this does not prove authenticity.'
        return 'Manual Review Required', 'No camera metadata found. Screenshots and edited photos may also lack metadata.'
    except Exception:return 'Invalid Image', 'The uploaded file could not be read as an image.'

def gps_widget():
    try:
        from streamlit_geolocation import streamlit_geolocation
        return streamlit_geolocation()
    except Exception:
        st.info('Browser GPS component is not installed/available. Enter coordinates manually, or install requirements and refresh.')
        return None



def render_location_map(complaints_df, trucks_df):

    points = []

    # Dustbin / complaint GPS locations
    if complaints_df is not None and not complaints_df.empty:
        for _, r in complaints_df.iterrows():
            try:
                lat = float(r['latitude'])
                lon = float(r['longitude'])

                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    continue

                if lat == 0 and lon == 0:
                    continue

                points.append({
                    'latitude': lat,
                    'longitude': lon,
                    'marker_color': '#ef4444',
                    'Location Type': 'Dustbin / Complaint',
                    'Reference': f"Complaint #{r['id']}",
                    'Area': str(r['address']),
                    'Status': str(r['status'])
                })

            except (ValueError, TypeError, KeyError):
                continue

    # Collection truck GPS locations
    if trucks_df is not None and not trucks_df.empty:
        for _, t in trucks_df.iterrows():
            try:
                lat = float(t['current_lat'])
                lon = float(t['current_lon'])

                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    continue

                if lat == 0 and lon == 0:
                    continue

                points.append({
                    'latitude': lat,
                    'longitude': lon,
                    'marker_color': '#2563eb',
                    'Location Type': 'Collection Truck',
                    'Reference': str(t['truck_no']),
                    'Area': str(t['current_area'] or 'Not updated'),
                    'Status': str(t['status'])
                })

            except (ValueError, TypeError, KeyError):
                continue

    st.subheader('🗺️ Dustbin & Truck Locations')

    st.markdown(
        '🔴 **Dustbin / Complaint Locations**'
        ' &nbsp;&nbsp; 🔵 **Collection Truck Locations**',
        unsafe_allow_html=True
    )

    if points:

        map_df = pd.DataFrame(points)

        st.map(
            map_df,
            latitude='latitude',
            longitude='longitude',
            color='marker_color',
            use_container_width=True
        )

        st.subheader('📍 Location Details')

        st.dataframe(
            map_df[
                ['Location Type', 'Reference', 'Area',
                 'Status', 'latitude', 'longitude']
            ],
            hide_index=True,
            use_container_width=True
        )

    else:

        st.markdown("""
        <div style="
            background:#ffffff;
            border:2px solid #60a5fa;
            border-radius:12px;
            padding:20px;
            color:#b00000;
            text-align:center;
            font-weight:700;
        ">
            📍 No GPS Locations Available

        </div>
        """, unsafe_allow_html=True)

    st.caption(
        'Map displays saved GPS locations. '
        'Truck locations update when new GPS coordinates are saved. '
        'Automatic live tracking is not enabled.'
    )


# ---------------- Login ----------------
if 'auth' not in st.session_state: st.session_state.auth=None
if not st.session_state.auth:
    st.markdown('<h1 style="text-align:center">♻️ Smart Waste Management</h1><p style="text-align:center;color:#a9bdd8">Citizen complaints • Municipal operations • Admin control</p>',unsafe_allow_html=True)
    a,b,c=st.columns([1,1.2,1])
    with b:
        with st.container(border=True):
            st.subheader('Login')
            uname=st.text_input('Username'); pw=st.text_input('Password',type='password')
            if st.button('Login',use_container_width=True):
                u=rows('SELECT * FROM users WHERE username=? AND password=?',(uname,pw))
                if len(u):st.session_state.auth={'username':u.iloc[0].username,'role':u.iloc[0].role,'name':u.iloc[0]['name']};st.rerun()
                else:st.error('Invalid username or password')
            st.caption('Demo login credentials')
            st.code('User: user / user123\nMunicipality: municipal / muni123\nAdmin: admin / admin123')
    st.stop()

me=st.session_state.auth; role=me['role']
with st.sidebar:
    st.markdown('## ♻️ Smart City')
    st.write(f"**{me['name']}**")
    st.caption(f"Role: {role}")
    if role=='User': pages=['My Dashboard','Report a Dustbin','My Complaints']
    elif role=='Municipality': pages=['Municipal Dashboard','Worker Management','Truck Management','Complaint Register']
    else: pages=['Admin Dashboard','All Complaints','Assign Collection','Truck Tracking','Add Dustbin','User & Municipality Details','Reports']
    page=st.radio('NAVIGATION',pages)
    if st.button('Logout',use_container_width=True):st.session_state.auth=None;st.rerun()

# ---------------- User ----------------
if role=='User':
    mine=rows('SELECT * FROM complaints WHERE username=? ORDER BY id DESC',(me['username'],))
    if page=='My Dashboard':
        st.title('👋 Citizen Dashboard')
        a,b,c=st.columns(3);a.metric('My Complaints',len(mine));b.metric('Pending',int((mine.status!='Collected').sum()) if len(mine) else 0);c.metric('Collected',int((mine.status=='Collected').sum()) if len(mine) else 0)
        st.markdown("""
<div style="
    background:#10284b;
    border:1px solid #38bdf8;
    border-left:5px solid #38bdf8;
    border-radius:12px;
    padding:18px 20px;
    margin-top:18px;
    color:#eef5ff;
    font-size:15px;
    line-height:1.7;
">
    📢 <b style="color:#38bdf8;">Citizen Information</b><br>
    Dustbin overflow or waste issue kanipisthe photo + GPS location tho complaint submit cheyyandi.
</div>
""", unsafe_allow_html=True)
        if len(mine):st.dataframe(mine[['id','address','status','created_at']],hide_index=True,use_container_width=True)
    elif page=='Report a Dustbin':
        st.title('📸 Report a Dustbin / Waste Issue')
        st.write('Photo theesi upload cheyyandi. GPS permission allow chesthe location capture avutundi.')
        st.markdown('**GPS Location**')
        loc=gps_widget()
        lat_default=loc.get('latitude') if isinstance(loc,dict) else None
        lon_default=loc.get('longitude') if isinstance(loc,dict) else None
        with st.form('complaint_form'):
            desc=st.text_area('Issue description',placeholder='Example: Dustbin full / garbage dumped on road')
            photo=st.file_uploader('Upload dustbin photo',type=['jpg','jpeg','png','webp'])
            l1,l2=st.columns(2)
            lat=l1.number_input('Latitude',value=float(lat_default or 0.0),format='%.6f')
            lon=l2.number_input('Longitude',value=float(lon_default or 0.0),format='%.6f')
            address=st.text_input('Area / Address',placeholder='Street, area, landmark')
            submit=st.form_submit_button('Submit Complaint',use_container_width=True)
        if submit:
            if not desc.strip() or not photo:st.error('Description and photo are required.')
            elif lat==0 or lon==0:st.error('Valid GPS coordinates required. Allow GPS or enter coordinates manually.')
            else:
                data=photo.getvalue(); ph=digest(data); existing=rows('SELECT id FROM complaints WHERE photo_hash=?',(ph,))
                status,reason=image_screening(data)
                if len(existing) or similar_photo_exists(data):status='Possible Duplicate / Similar Photo – Manual Review'
                ext=photo.name.rsplit('.',1)[-1].lower()
                if ext not in {'jpg','jpeg','png','webp'}:
                    st.error('Unsupported image extension.')
                    st.stop()
                safe_user=re.sub(r'[^A-Za-z0-9_-]','_',me['username'])
                filename=f"complaint_{safe_user}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{ph[:8]}.{ext}" 
                path=os.path.join(UPLOAD_DIR,filename)
                with open(path,'wb') as f:f.write(data)
                run('INSERT INTO complaints(username,description,photo,photo_hash,verification,latitude,longitude,address,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (me['username'],desc.strip(),os.path.relpath(path,os.path.dirname(__file__)),ph,status,float(lat),float(lon),address.strip() or 'Address not provided','New',datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                st.success('Complaint submitted! Your complaint count has increased.')
                st.warning(f'Photo screening: {status}. {reason} This is a basic screening, not a guarantee that an image is real or fake.')
                st.rerun()
    else:
        st.title('🧾 My Complaints')
        
        if mine.empty:
            st.markdown("""
            <div style="
                background:#10284b;
                border:1px solid #38bdf8;
                border-left:5px solid #38bdf8;
                border-radius:12px;
                padding:22px;
                margin-top:15px;
                color:#ffffff;
                font-size:16px;
                line-height:1.8;
            ">
                <h3 style="color:#38bdf8 !important; margin:0 0 10px 0;">
                    📭 No Complaints Found
                </h3>
                <p style="color:#ffffff !important; margin:0;">
                    You have not submitted any complaints yet.
                </p>
                <p style="color:#ffffff !important; margin:8px 0 0 0;">
                    Go to <b style="color:#38bdf8;">Report a Dustbin</b>
                    to upload a waste issue photo and GPS location.
                </p>
            </div>
            """, unsafe_allow_html=True)
        else:
            for _,r in mine.iterrows():
                with st.expander(f"Complaint #{r.id} · {r.status} · {r.created_at}"):
                    st.write(r.description);st.write(f"Location: {r.address} ({r.latitude}, {r.longitude})")
                    st.write(f"Photo check: {r.verification}")
                    p=os.path.join(os.path.dirname(__file__),r.photo)
                    if os.path.exists(p):st.image(p,width=300)
                    st.write(f"Assigned truck: {r.assigned_truck or 'Not assigned yet'} | Driver: {r.assigned_driver or 'Not assigned yet'}")

# ---------------- Municipality ----------------
elif role=='Municipality':
    if page=='Municipal Dashboard':
        st.title('🏛️ Municipality Dashboard')
        comp=rows('SELECT * FROM complaints');worker=rows('SELECT * FROM workers');fleet=rows('SELECT * FROM trucks')
        a,b,c,d=st.columns(4);a.metric('Total Complaints',len(comp));b.metric('Active Workers',int((worker.status=='Active').sum()) if len(worker) else 0);c.metric('Total Trucks',len(fleet));d.metric('Pending Tasks',int((comp.status!='Collected').sum()) if len(comp) else 0)
        render_location_map(comp, fleet)
        st.subheader('Latest Citizen Complaints')
        if len(comp):
            comp_with_phone=comp.merge(rows('SELECT username,phone FROM users'),on='username',how='left')
            st.dataframe(comp_with_phone[['id','username','phone','address','status','assigned_truck','created_at']].tail(15),hide_index=True,use_container_width=True)
        st.subheader('Admin / System Account Details')
        st.dataframe(rows("SELECT username,name,phone,role FROM users WHERE role='Admin'"),hide_index=True,use_container_width=True)
    elif page=='Worker Management':
        st.title('👷 Worker Management')
        st.dataframe(rows('SELECT * FROM workers'),hide_index=True,use_container_width=True)
        with st.expander('Add Worker'):
            with st.form('add_worker'):
                n=st.text_input('Worker name');p=st.text_input('Phone');r=st.selectbox('Role',['Sanitation Worker','Driver','Supervisor']);sh=st.selectbox('Shift',['Morning','Evening','Night','Day']);s=st.selectbox('Status',['Active','Leave','Inactive'])
                if st.form_submit_button('Add Worker'):
                    if n and p:run('INSERT INTO workers(name,phone,role,shift,status) VALUES(?,?,?,?,?)',(n,p,r,sh,s));st.success('Worker added');st.rerun()
                    else:st.error('Enter name and phone')
        st.subheader('Update Worker Status')
        w=rows('SELECT * FROM workers')
        if len(w):
            wid=st.selectbox('Worker',w.id,format_func=lambda x:f"{w[w.id==x].iloc[0]['name']} (ID {x})")
            ws=st.selectbox('New status',['Active','Leave','Inactive'])
            if st.button('Update Worker'):run('UPDATE workers SET status=? WHERE id=?',(ws,int(wid)));st.rerun()
    elif page=='Truck Management':
        st.title('🚛 Truck Management');st.dataframe(rows('SELECT * FROM trucks'),hide_index=True,use_container_width=True)
        with st.expander('Add Truck'):
            with st.form('add_truck'):
                no=st.text_input('Truck number');dr=st.text_input('Driver name');ph=st.text_input('Driver phone')
                if st.form_submit_button('Add Truck'):
                    try:run('INSERT INTO trucks(truck_no,driver,phone,status,current_area) VALUES(?,?,? ,?,?)',(no,dr,ph,'Available','Depot'));st.success('Truck added');st.rerun()
                    except Exception:st.error('Truck number already exists or invalid data.')
        st.subheader('📍 Update Truck GPS Location')
        current_fleet=rows('SELECT * FROM trucks ORDER BY truck_no')
        if len(current_fleet):
            selected_truck=st.selectbox('Select truck for location update',current_fleet.id,
                format_func=lambda x:f"{current_fleet[current_fleet.id==x].iloc[0]['truck_no']} — {current_fleet[current_fleet.id==x].iloc[0]['driver']}",
                key='municipal_location_truck')
            selected_row=current_fleet[current_fleet.id==selected_truck].iloc[0]
            with st.form('municipal_truck_gps_update'):
                gps1,gps2=st.columns(2)
                truck_lat=gps1.number_input('Truck latitude',value=float(selected_row.current_lat or 0),format='%.6f')
                truck_lon=gps2.number_input('Truck longitude',value=float(selected_row.current_lon or 0),format='%.6f')
                truck_area=st.text_input('Truck current area',value=selected_row.current_area or '')
                if st.form_submit_button('Save Truck Location',use_container_width=True):
                    if not (-90 <= truck_lat <= 90 and -180 <= truck_lon <= 180) or (truck_lat == 0 and truck_lon == 0):
                        st.error('Valid GPS latitude and longitude enter cheyyandi.')
                    else:
                        run('UPDATE trucks SET current_lat=?,current_lon=?,current_area=? WHERE id=?',
                            (float(truck_lat),float(truck_lon),truck_area.strip(),int(selected_truck)))
                        st.success('Truck GPS location saved. Municipality map lo latest location kanipistundi.')
                        st.rerun()
        else:
            st.info('First add a truck to update its GPS location.')
    else:
        st.title('📋 Complaint Register');comp=rows('SELECT * FROM complaints ORDER BY id DESC')
        if len(comp):
            comp_view=comp.merge(rows('SELECT username,phone FROM users'),on='username',how='left')
            st.dataframe(comp_view[['id','username','phone','description','address','latitude','longitude','verification','status','assigned_truck','assigned_driver']],hide_index=True,use_container_width=True)
            st.caption('Municipality can view complaints and operational status. Admin performs final truck assignment.')
            resolved=comp[comp.status=='Collected']
            if len(resolved):
                delete_id=st.selectbox('Select resolved complaint to delete',resolved.id,key='municipal_delete_complaint')
                if st.button('Delete resolved complaint',type='secondary'):
                    photo_row=comp[comp.id==delete_id].iloc[0]
                    photo_path=os.path.join(os.path.dirname(__file__),str(photo_row.photo or ''))
                    run('DELETE FROM complaints WHERE id=? AND status=?',(int(delete_id),'Collected'))
                    if os.path.isfile(photo_path):
                        try:
                            os.remove(photo_path)
                        except OSError:
                            st.warning('Complaint deleted, but its stored photo could not be removed.')
                    st.success(f'Resolved complaint #{delete_id} deleted.')
                    st.rerun()
            else:
                st.info('Only complaints marked Collected can be deleted.')
        else:st.info('No complaints yet.')

# ---------------- Admin ----------------
else:
    if page=='Admin Dashboard':
        st.title('🛡️ Admin Control Center')
        comp=rows('SELECT * FROM complaints');fleet=rows('SELECT * FROM trucks')
        a,b,c,d=st.columns(4);a.metric('Total Reports',len(comp));b.metric('New / Pending',int((comp.status=='New').sum()) if len(comp) else 0);c.metric('Active Trucks',int((fleet.status=='On Route').sum()) if len(fleet) else 0);d.metric('Collected Reports',int((comp.status=='Collected').sum()) if len(comp) else 0)
        st.subheader('Recent complaints')
        if len(comp):st.dataframe(comp[['id','username','address','status','assigned_truck','created_at']].tail(20),hide_index=True,use_container_width=True)
        st.info('Select Assign Collection to inspect complaint photo, verify its location and assign an available truck/driver.')
    elif page=='All Complaints':
        st.title('🗂️ All Citizen Complaints');comp=rows('SELECT * FROM complaints ORDER BY id DESC')
        if comp.empty:st.info('No complaints submitted.')
        else:
            comp_view=comp.merge(rows('SELECT username,phone FROM users'),on='username',how='left')
            st.dataframe(comp_view[['id','username','phone','description','address','latitude','longitude','verification','status','created_at']],hide_index=True,use_container_width=True)
            cid=st.selectbox('View complaint',comp.id)
            r=comp[comp.id==cid].iloc[0]
            st.write(f"**Issue:** {r.description} | **Reporter:** {r.username}")
            st.write(f"**Location:** {r.address} | GPS: {r.latitude}, {r.longitude}")
            st.write(f"**Photo screening:** {r.verification}")
            fp=os.path.join(os.path.dirname(__file__),r.photo)
            if os.path.exists(fp):st.image(fp,width=450)
            st.markdown(f"[Open GPS location in map](https://www.google.com/maps?q={r.latitude},{r.longitude})")
    elif page=='Assign Collection':
        st.title('📍 Assign Driver to Reported Dustbin');comp=rows("SELECT * FROM complaints WHERE status!='Collected' ORDER BY id DESC");fleet=rows("SELECT * FROM trucks WHERE status!='Maintenance'")
        if comp.empty:st.success('All complaints are collected, or no complaints have been submitted.')
        else:
            cid=st.selectbox('Select complaint',comp.id,format_func=lambda x:f"Complaint #{x} — {comp[comp.id==x].iloc[0]['address']} ({comp[comp.id==x].iloc[0]['status']})")
            r=comp[comp.id==cid].iloc[0]
            st.markdown(f"**User:** {r.username}  \n**Issue:** {r.description}  \n**Reported location:** {r.address}  \n**Coordinates:** {r.latitude}, {r.longitude}")
            fp=os.path.join(os.path.dirname(__file__),r.photo)
            if os.path.exists(fp):st.image(fp,width=350)
            st.write(f"Photo screening: {r.verification}")
            st.markdown(f"[📍 Navigate to complaint location](https://www.google.com/maps/dir/?api=1&destination={r.latitude},{r.longitude})")
            if fleet.empty:st.warning('No trucks available. Add a truck or change its status in Municipal Truck Management.')
            else:
                tid=st.selectbox('Assign truck',fleet.id,format_func=lambda x:f"{fleet[fleet.id==x].iloc[0]['truck_no']} — Driver: {fleet[fleet.id==x].iloc[0]['driver']}")
                selected_fleet_truck=fleet[fleet.id==tid].iloc[0]
                if pd.notna(selected_fleet_truck.current_lat) and pd.notna(selected_fleet_truck.current_lon):
                    st.markdown(f"[🧭 Navigate from selected truck's latest GPS position](https://www.google.com/maps/dir/?api=1&origin={selected_fleet_truck.current_lat},{selected_fleet_truck.current_lon}&destination={r.latitude},{r.longitude})")
                status=st.selectbox('Task status',['Assigned','On Route','Collected'])
                if st.button('Save Assignment',use_container_width=True):
                    t=fleet[fleet.id==tid].iloc[0]
                    run('UPDATE complaints SET assigned_truck=?,assigned_driver=?,status=?,completed_at=? WHERE id=?',(t.truck_no,t.driver,status,datetime.now().strftime('%Y-%m-%d %H:%M:%S') if status=='Collected' else None,int(cid)))
                    run('UPDATE trucks SET status=?,current_area=? WHERE id=?',('Available' if status=='Collected' else 'On Route',r.address,int(tid)))
                    st.success(f"{t.driver} assigned to complaint #{cid} at {r.address}");st.rerun()
    elif page=='Truck Tracking':
        st.title('🚚 Truck Tracking & Driver Location');fleet=rows('SELECT * FROM trucks')
        st.caption('This screen displays the latest saved GPS coordinates. For continuous live tracking, the driver must share GPS from their phone through a deployed location-update service; this prototype does not run background tracking.')
        if len(fleet):
            render_location_map(pd.DataFrame(), fleet)
            st.dataframe(fleet,hide_index=True,use_container_width=True)
            tid=st.selectbox('Select truck',fleet.id,format_func=lambda x:fleet[fleet.id==x].iloc[0]['truck_no'])
            t=fleet[fleet.id==tid].iloc[0]
            st.markdown('**Update this truck from the device currently signed in**')
            device_loc=gps_widget()
            if isinstance(device_loc,dict) and device_loc.get('latitude') is not None and device_loc.get('longitude') is not None:
                if st.button('Save this device GPS as truck location'):
                    run('UPDATE trucks SET current_lat=?,current_lon=?,current_area=? WHERE id=?',
                        (float(device_loc['latitude']),float(device_loc['longitude']),t.current_area or 'GPS location',int(tid)))
                    st.success('Latest device GPS saved for this truck.')
                    st.rerun()
            with st.form('truck_gps'):
                la=st.number_input('Driver current latitude',value=float(t.current_lat or 0),format='%.6f');lo=st.number_input('Driver current longitude',value=float(t.current_lon or 0),format='%.6f');area=st.text_input('Current area',value=t.current_area or '')
                if st.form_submit_button('Update truck location manually'):
                    if not (-90 <= la <= 90 and -180 <= lo <= 180) or (la == 0 and lo == 0):
                        st.error('Enter valid latitude and longitude.')
                    else:
                        run('UPDATE trucks SET current_lat=?,current_lon=?,current_area=? WHERE id=?',(la,lo,area,int(tid)))
                        st.success('Truck location updated.')
                        st.rerun()
            if pd.notna(t.current_lat) and pd.notna(t.current_lon) and float(t.current_lat)!=0 and float(t.current_lon)!=0:
                st.markdown(f"[Open truck's latest location in Google Maps](https://www.google.com/maps?q={t.current_lat},{t.current_lon})")
                assigned=rows("SELECT * FROM complaints WHERE assigned_truck=? AND status!='Collected' ORDER BY id DESC",(t.truck_no,))
                if len(assigned):
                    task=assigned.iloc[0]
                    st.markdown(f"[🧭 Navigate from this truck to complaint #{task.id}](https://www.google.com/maps/dir/?api=1&origin={t.current_lat},{t.current_lon}&destination={task.latitude},{task.longitude})")
            else:
                st.info('No valid GPS coordinates saved for this truck yet.')
    elif page=='Add Dustbin':
        st.title('🗑️ Add / Manage Public Dustbins')
        dustbins=rows('SELECT * FROM dustbins ORDER BY id DESC')
        if not dustbins.empty:
            st.dataframe(dustbins,hide_index=True,use_container_width=True)
            st.subheader('Dustbin locations on map')
            st.map(dustbins.rename(columns={'latitude':'lat','longitude':'lon'}),latitude='lat',longitude='lon')
            selected_bin=st.selectbox('Select dustbin to remove',dustbins.id,key='remove_dustbin_id')
            if st.button('Delete selected dustbin'):
                run('DELETE FROM dustbins WHERE id=?',(int(selected_bin),))
                st.success('Dustbin removed.')
                st.rerun()
        else:
            st.info('No dustbins added yet.')
        with st.form('admin_add_dustbin'):
            bin_name=st.text_input('Dustbin name / ID')
            bin_area=st.text_input('Area / address')
            d1,d2=st.columns(2)
            bin_lat=d1.number_input('Latitude',format='%.6f')
            bin_lon=d2.number_input('Longitude',format='%.6f')
            bin_status=st.selectbox('Status',['Active','Needs Cleaning','Damaged'])
            if st.form_submit_button('Add Dustbin'):
                if not bin_name.strip() or not bin_area.strip():
                    st.error('Enter dustbin name and area.')
                elif not (-90 <= bin_lat <= 90 and -180 <= bin_lon <= 180) or (bin_lat == 0 and bin_lon == 0):
                    st.error('Enter valid GPS coordinates.')
                else:
                    run('INSERT INTO dustbins(name,area,latitude,longitude,status,created_at) VALUES(?,?,?,?,?,?)',
                        (bin_name.strip(),bin_area.strip(),float(bin_lat),float(bin_lon),bin_status,datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    st.success('Dustbin added successfully.')
                    st.rerun()
    elif page=='User & Municipality Details':
        st.title('👥 User & Municipality Details')
        st.subheader('Registered accounts');st.dataframe(rows('SELECT username,role,name,phone FROM users'),hide_index=True,use_container_width=True)
        with st.expander('Create login account'):
            with st.form('new_account'):
                un=st.text_input('Username');pw=st.text_input('Temporary password');nm=st.text_input('Full name');phone=st.text_input('Phone');rr=st.selectbox('Role',['User','Municipality','Admin'])
                if st.form_submit_button('Create account'):
                    try:
                        if not un or not pw or not nm:st.error('Username, password and name are required.')
                        else:run('INSERT INTO users VALUES(?,?,?,?,?)',(un,pw,rr,nm,phone));st.success('Account created');st.rerun()
                    except Exception:st.error('Username already exists.')
    else:
        st.title('📊 Reports & Analytics');comp=rows('SELECT * FROM complaints')
        if len(comp):
            st.bar_chart(comp.status.value_counts());st.dataframe(comp[['id','username','address','status','created_at']],hide_index=True,use_container_width=True)
            st.download_button('Download complaint report CSV',comp.to_csv(index=False).encode('utf-8'),'complaints.csv','text/csv')
        else:st.info('No report data yet.')

st.markdown('<hr><p style="text-align:center;color:#829bbd;font-size:11px">Smart Waste Management · Role-based demo application</p>',unsafe_allow_html=True)
