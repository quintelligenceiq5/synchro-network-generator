"""
Synchro Network Generator - Streamlit Web Application
Generates Synchro-compatible files with automatic backup to Google Drive
"""

import streamlit as st
import requests
import math
from datetime import datetime
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import gspread

# Page configuration
st.set_page_config(
    page_title="Synchro Network Generator",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .step-header {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .success-box {
        background-color: #d4edda;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #28a745;
    }
</style>
""", unsafe_allow_html=True)

class SynchroGenerator:
    def __init__(self):
        self.standard_approach_distance = 1500
        self.node_counter = 0
        self.origin_lat = None
        self.origin_lon = None
        
    def parse_intersection_name(self, intersection_name):
        """Parse intersection name to extract street names"""
        separators = [' and ', ' & ', ' at ', ' @ ']
        
        street1, street2, location = None, None, None
        
        for sep in separators:
            if sep in intersection_name.lower():
                parts = intersection_name.split(sep, 1)
                if len(parts) == 2:
                    street1_parts = parts[0].strip().split(',')
                    street1 = street1_parts[0].strip()
                    
                    street2_parts = parts[1].strip().split(',')
                    street2 = street2_parts[0].strip()
                    
                    if len(street2_parts) > 1:
                        location = ', '.join(street2_parts[1:]).strip()
                    elif len(street1_parts) > 1:
                        location = ', '.join(street1_parts[1:]).strip()
                    
                    break
        
        return street1, street2, location
    
    def geocode_intersection(self, intersection_name):
        """Geocode using ArcGIS"""
        url = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
        params = {'f': 'json', 'singleLine': intersection_name, 'maxLocations': 1}
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('candidates'):
                    location = data['candidates'][0]['location']
                    lat, lon = location['y'], location['x']
                    address = data['candidates'][0]['address']
                    return lat, lon, address
        except:
            pass
        
        return None, None, None
    
    def latlon_to_local(self, lat, lon):
        """Convert lat/lon to local feet coordinates"""
        if self.origin_lat is None:
            self.origin_lat, self.origin_lon = lat, lon
            return 0, 0
        
        lat_feet = 364000
        lon_feet = 364000 * math.cos(math.radians(self.origin_lat))
        x = int((lon - self.origin_lon) * lon_feet)
        y = int((lat - self.origin_lat) * lat_feet)
        return x, y
    
    def generate_network(self, intersections_data):
        """Generate complete Synchro network file"""
        all_nodes = []
        links = []
        intersections = []
        
        # Process each intersection
        for idx, int_data in enumerate(intersections_data):
            # Geocode
            lat, lon, address = self.geocode_intersection(int_data['name'])
            if not lat or not lon:
                continue
            
            x, y = self.latlon_to_local(lat, lon)
            
            # Parse streets
            street1, street2, location = self.parse_intersection_name(int_data['name'])
            
            # Create center node
            self.node_counter += 1
            center_id = self.node_counter
            center_node = {
                'id': center_id,
                'type': 1,
                'x': x,
                'y': y,
                'z': 0,
                'name': int_data['name'],
                'street_ns': street1,
                'street_ew': street2,
                'lat': lat,
                'lon': lon
            }
            all_nodes.append(center_node)
            
            # Create approach nodes
            approaches = []
            directions = {
                'NB': (0, self.standard_approach_distance),
                'SB': (0, -self.standard_approach_distance),
                'EB': (self.standard_approach_distance, 0),
                'WB': (-self.standard_approach_distance, 0)
            }
            
            for direction, (dx, dy) in directions.items():
                self.node_counter += 1
                approach_node = {
                    'id': self.node_counter,
                    'type': 0,
                    'x': x + dx,
                    'y': y + dy,
                    'z': 0,
                    'direction': direction,
                    'center_node': center_id
                }
                all_nodes.append(approach_node)
                approaches.append(approach_node)
            
            # Store intersection data
            intersection = {
                'center_node': center_node,
                'approaches': approaches,
                'config': int_data
            }
            intersections.append(intersection)
            
            # Create links
            for approach in approaches:
                direction = approach['direction']
                
                links.append({
                    'from_node': approach['id'],
                    'to_node': center_id,
                    'direction': direction,
                    'lanes': int_data['lanes'][direction],
                    'distance': self.standard_approach_distance,
                    'speed': int_data['speed'][direction],
                    'twltl': int_data['twltl'][direction]
                })
                
                opposite = {'NB': 'SB', 'SB': 'NB', 'EB': 'WB', 'WB': 'EB'}[direction]
                links.append({
                    'from_node': center_id,
                    'to_node': approach['id'],
                    'direction': opposite,
                    'lanes': int_data['lanes'][opposite],
                    'distance': self.standard_approach_distance,
                    'speed': int_data['speed'][opposite],
                    'twltl': int_data['twltl'][opposite]
                })
        
        return self.generate_file_content(all_nodes, links, intersections)
    
    def generate_file_content(self, all_nodes, links, intersections):
        """Generate Synchro file content"""
        output = io.StringIO()
        
        # NETWORK SECTION
        output.write("[Network]\t\t\t\t\t\t\t\t\n")
        output.write("Network Settings\t\t\t\t\t\t\t\t\n")
        output.write("RECORDNAME\tDATA\t\t\t\t\t\t\t\n")
        output.write("UTDFVERSION\t8\t\t\t\t\t\t\t\n")
        output.write("Metric\t0\t\t\t\t\t\t\t\n")
        output.write("yellowTime\t3.5\t\t\t\t\t\t\t\n")
        output.write("allRedTime\t1\t\t\t\t\t\t\t\n")
        output.write("Walk\t7\t\t\t\t\t\t\t\n")
        output.write("DontWalk\t11\t\t\t\t\t\t\t\n")
        output.write("HV\t0.02\t\t\t\t\t\t\t\n")
        output.write("PHF\t0.92\t\t\t\t\t\t\t\n")
        output.write("DefWidth\t12\t\t\t\t\t\t\t\n")
        output.write("DefFlow\t1900\t\t\t\t\t\t\t\n")
        output.write("vehLength\t25\t\t\t\t\t\t\t\n")
        output.write("heavyvehlength\t45\t\t\t\t\t\t\t\n")
        output.write("criticalgap\t4.5\t\t\t\t\t\t\t\n")
        output.write("followuptime\t2.5\t\t\t\t\t\t\t\n")
        output.write("stopthresholdspeed\t5\t\t\t\t\t\t\t\n")
        output.write("criticalmergegap\t3.7\t\t\t\t\t\t\t\n")
        output.write("growth\t1\t\t\t\t\t\t\t\n")
        output.write("PedSpeed\t3.5\t\t\t\t\t\t\t\n")
        output.write("LostTimeAdjust\t0\t\t\t\t\t\t\t\n")
        output.write(f"ScenarioDate\t{datetime.now().strftime('%m/%d/%Y')}\t\t\t\t\t\t\t\n")
        output.write(f"ScenarioTime\t{datetime.now().strftime('%I:%M %p')}\t\t\t\t\t\t\t\n")
        output.write("\t\t\t\t\t\t\t\t\n")
        
        # NODES SECTION
        output.write("[Nodes]\t\t\t\t\t\t\t\t\n")
        output.write("Node Data\t\t\t\t\t\t\t\t\n")
        output.write("INTID\tTYPE\tX\tY\tZ\tDESCRIPTION\tCBD\tInside Radius\tOutside Radius\tRoundabout Lanes\tCircle Speed\t\t\t\n")
        
        for node in all_nodes:
            output.write(f"{node['id']}\t{node['type']}\t{node['x']}\t{node['y']}\t{node['z']}\t\t\t\t\t\t\t\t\t\n")
        
        output.write("\t\t\t\t\t\t\t\t\n")
        
        # LINKS SECTION
        output.write("[Links]\t\t\t\t\t\t\t\t\n")
        output.write("Link Data\t\t\t\t\t\t\t\t\n")
        output.write("RECORDNAME\tINTID\tNB\tSB\tEB\tWB\t\t\t\t\n")
        
        links_by_node = {}
        for link in links:
            up = link['from_node']
            if up not in links_by_node:
                links_by_node[up] = {'NB': None, 'SB': None, 'EB': None, 'WB': None}
            links_by_node[up][link['direction']] = link
        
        for up_node_id in sorted(links_by_node.keys()):
            dirs = links_by_node[up_node_id]
            
            output.write(f"Up ID\t{up_node_id}\t")
            output.write(f"{dirs['NB']['to_node'] if dirs['NB'] else ''}\t")
            output.write(f"{dirs['SB']['to_node'] if dirs['SB'] else ''}\t")
            output.write(f"{dirs['EB']['to_node'] if dirs['EB'] else ''}\t")
            output.write(f"{dirs['WB']['to_node'] if dirs['WB'] else ''}\t\t\t\t\n")
            
            output.write(f"Lanes\t{up_node_id}\t")
            output.write(f"{dirs['NB']['lanes'] if dirs['NB'] else ''}\t")
            output.write(f"{dirs['SB']['lanes'] if dirs['SB'] else ''}\t")
            output.write(f"{dirs['EB']['lanes'] if dirs['EB'] else ''}\t")
            output.write(f"{dirs['WB']['lanes'] if dirs['WB'] else ''}\t\t\t\t\n")
            
            # Street names
            node_obj = next((n for n in all_nodes if n['id'] == up_node_id), None)
            street_ns, street_ew = "", ""
            
            if node_obj:
                if node_obj.get('type') == 1:
                    street_ns = node_obj.get('street_ns', '')
                    street_ew = node_obj.get('street_ew', '')
                else:
                    for intersection in intersections:
                        if any(a['id'] == up_node_id for a in intersection['approaches']):
                            street_ns = intersection['center_node'].get('street_ns', '')
                            street_ew = intersection['center_node'].get('street_ew', '')
                            break
            
            output.write(f"Name\t{up_node_id}\t")
            output.write(f"{street_ns if dirs['NB'] else ''}\t")
            output.write(f"{street_ns if dirs['SB'] else ''}\t")
            output.write(f"{street_ew if dirs['EB'] else ''}\t")
            output.write(f"{street_ew if dirs['WB'] else ''}\t\t\t\t\n")
            
            output.write(f"Distance\t{up_node_id}\t")
            for d in ['NB', 'SB', 'EB', 'WB']:
                output.write(f"{dirs[d]['distance'] if dirs[d] else ''}\t")
            output.write("\t\t\t\n")
            
            output.write(f"Speed\t{up_node_id}\t")
            for d in ['NB', 'SB', 'EB', 'WB']:
                output.write(f"{dirs[d]['speed'] if dirs[d] else ''}\t")
            output.write("\t\t\t\n")
            
            output.write(f"Time\t{up_node_id}\t")
            for d in ['NB', 'SB', 'EB', 'WB']:
                if dirs[d]:
                    time_val = dirs[d]['distance'] / dirs[d]['speed'] * 3600 / 5280
                    output.write(f"{time_val:.1f}\t")
                else:
                    output.write("\t")
            output.write("\t\t\t\n")
            
            output.write(f"Grade\t{up_node_id}\t0\t0\t0\t0\t\t\t\t\n")
            output.write(f"Median\t{up_node_id}\t12\t12\t12\t12\t\t\t\t\n")
            output.write(f"Offset\t{up_node_id}\t0\t0\t0\t0\t\t\t\t\n")
            
            output.write(f"TWLTL\t{up_node_id}\t")
            for d in ['NB', 'SB', 'EB', 'WB']:
                output.write(f"{dirs[d].get('twltl', 0) if dirs[d] else ''}\t")
            output.write("\t\t\t\n")
            
            output.write(f"Crosswalk Width\t{up_node_id}\t16\t16\t16\t16\t\t\t\t\n")
            output.write(f"Mandatory Distance\t{up_node_id}\t200\t200\t200\t200\t\t\t\t\n")
            output.write(f"Mandatory Distance2\t{up_node_id}\t1320\t1320\t1320\t1320\t\t\t\t\n")
            output.write(f"Positioning Distance\t{up_node_id}\t880\t880\t880\t880\t\t\t\t\n")
            output.write(f"Positioning Distance2\t{up_node_id}\t1760\t1760\t1760\t1760\t\t\t\t\n")
            output.write(f"Curve Pt X\t{up_node_id}\t\t\t\t\t\t\t\t\n")
            output.write(f"Curve Pt Y\t{up_node_id}\t\t\t\t\t\t\t\t\n")
            output.write(f"Curve Pt Z\t{up_node_id}\t\t\t\t\t\t\t\t\n")
            output.write(f"Link Is Hidden\t{up_node_id}\tFALSE\tFALSE\tFALSE\tFALSE\t\t\t\t\n")
            output.write(f"Street Name Is Hidden\t{up_node_id}\tFALSE\tFALSE\tFALSE\tFALSE\t\t\t\t\n")
        
        output.write("\t\t\t\t\t\t\t\t\n")
        
        # LANES SECTION (simplified)
        output.write("[Lanes]\t\t\t\t\t\t\t\t\n")
        output.write("Lane Group Data\t\t\t\t\t\t\t\t\n")
        output.write("RECORDNAME\tINTID\tNBL\tNBT\tNBR\tSBL\tSBT\tSBR\tEBL\tEBT\tEBR\tWBL\tWBT\tWBR\tPED\tHOLD\n")
        output.write("\t\t\t\t\t\t\t\t\n")
        
        # TIMEPLANS SECTION (simplified)
        output.write("[Timeplans]\t\t\t\t\t\t\t\t\n")
        output.write("Timing Plan Settings\t\t\t\t\t\t\t\t\n")
        output.write("RECORDNAME\tINTID\tDATA\t\t\t\t\t\t\n")
        output.write("\t\t\t\t\t\t\t\t\n")
        
        # PHASES SECTION (simplified)
        output.write("[Phases]\t\t\t\t\t\t\t\t\n")
        output.write("Phasing Data\t\t\t\t\t\t\t\t\n")
        output.write("RECORDNAME\tINTID\tD1\tD2\tD3\tD4\tD5\tD6\tD7\tD8\t\t\t\t\n")
        output.write("\t\t\t\t\t\t\t\t\n")
        
        return output.getvalue()

def save_to_google_drive(filename, content, user_email):
    """Save file to Google Drive"""
    try:
        creds_dict = json.loads(st.secrets["google_credentials"])
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        
        service = build('drive', 'v3', credentials=creds)
        
        folder_id = st.secrets["google_drive_folder_id"]
        
        file_metadata = {
            'name': f"{user_email}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}",
            'parents': [folder_id]
        }
        
        media = MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype='text/plain', resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id,webViewLink').execute()
        
        return file.get('webViewLink')
    except Exception as e:
        st.error(f"Error saving to Google Drive: {e}")
        return None

def log_to_google_sheets(user_email, intersections, file_link, status):
    """Log generation to Google Sheets"""
    try:
        creds_dict = json.loads(st.secrets["google_credentials"])
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        
        client = gspread.authorize(creds)
        sheet = client.open_by_key(st.secrets["google_sheet_id"]).sheet1
        
        sheet.append_row([
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            user_email,
            ', '.join(intersections),
            file_link or 'N/A',
            status
        ])
    except Exception as e:
        st.error(f"Error logging to Google Sheets: {e}")

# Main App
def main():
    st.markdown('<h1 class="main-header">🚦 Synchro Network Generator</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    **Welcome!** This tool automatically generates Synchro-compatible network files.
    
    **Features:**
    - 🌍 Automatic geocoding of intersections
    - 📊 Complete network configuration
    - 💾 Auto-backup to Google Drive
    - 📝 Usage tracking
    """)
    
    # Sidebar
    with st.sidebar:
        st.header("📋 Instructions")
        st.markdown("""
        **Format:** `NS_Street and EW_Street, City, State`
        
        **Example:**
        - Haggerty Road and 10 Mile Road, Novi, Michigan
        - Main Street and Oak Avenue, Detroit, Michigan
        
        **Legend:**
        - First street = NB/SB
        - Second street = EB/WB
        """)
        
        user_email = st.text_input("Your Email:", placeholder="user@company.com")
    
    # Initialize session state
    if 'intersections_data' not in st.session_state:
        st.session_state.intersections_data = []
    
    # Step 1: Add Intersections
    st.markdown('<div class="step-header"><h2>Step 1: Add Intersections</h2></div>', unsafe_allow_html=True)
    
    with st.form("add_intersection_form"):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            intersection_name = st.text_input(
                "Intersection Name:",
                placeholder="Haggerty Road and 10 Mile Road, Novi, Michigan"
            )
        
        with col2:
            add_button = st.form_submit_button("➕ Add Intersection", use_container_width=True)
        
        if add_button and intersection_name:
            with st.spinner("Configuring intersection..."):
                # Create configuration form
                st.subheader(f"Configuration for: {intersection_name}")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.write("**Northbound**")
                    nb_lanes = st.number_input("Lanes", min_value=1, max_value=6, value=2, key="nb_lanes")
                    nb_speed = st.number_input("Speed (mph)", min_value=15, max_value=70, value=30, key="nb_speed")
                    nb_twltl = 1 if st.checkbox("TWLTL", key="nb_twltl") else 0
                
                with col2:
                    st.write("**Southbound**")
                    sb_lanes = st.number_input("Lanes", min_value=1, max_value=6, value=2, key="sb_lanes")
                    sb_speed = st.number_input("Speed (mph)", min_value=15, max_value=70, value=30, key="sb_speed")
                    sb_twltl = 1 if st.checkbox("TWLTL", key="sb_twltl") else 0
                
                with col3:
                    st.write("**Eastbound**")
                    eb_lanes = st.number_input("Lanes", min_value=1, max_value=6, value=2, key="eb_lanes")
                    eb_speed = st.number_input("Speed (mph)", min_value=15, max_value=70, value=30, key="eb_speed")
                    eb_twltl = 1 if st.checkbox("TWLTL", key="eb_twltl") else 0
                
                with col4:
                    st.write("**Westbound**")
                    wb_lanes = st.number_input("Lanes", min_value=1, max_value=6, value=2, key="wb_lanes")
                    wb_speed = st.number_input("Speed (mph)", min_value=15, max_value=70, value=30, key="wb_speed")
                    wb_twltl = 1 if st.checkbox("TWLTL", key="wb_twltl") else 0
                
                confirm_add = st.form_submit_button("✅ Confirm & Add", use_container_width=True)
                
                if confirm_add:
                    int_data = {
                        'name': intersection_name,
                        'lanes': {'NB': nb_lanes, 'SB': sb_lanes, 'EB': eb_lanes, 'WB': wb_lanes},
                        'speed': {'NB': nb_speed, 'SB': sb_speed, 'EB': eb_speed, 'WB': wb_speed},
                        'twltl': {'NB': nb_twltl, 'SB': sb_twltl, 'EB': eb_twltl, 'WB': wb_twltl}
                    }
                    st.session_state.intersections_data.append(int_data)
                    st.success(f"✅ Added: {intersection_name}")
                    st.rerun()
    
    # Display added intersections
    if st.session_state.intersections_data:
        st.markdown("### Added Intersections:")
        for idx, int_data in enumerate(st.session_state.intersections_data):
            with st.expander(f"{idx+1}. {int_data['name']}"):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("NB Lanes", int_data['lanes']['NB'])
                col2.metric("SB Lanes", int_data['lanes']['SB'])
                col3.metric("EB Lanes", int_data['lanes']['EB'])
                col4.metric("WB Lanes", int_data['lanes']['WB'])
                
                if st.button(f"🗑️ Remove", key=f"remove_{idx}"):
                    st.session_state.intersections_data.pop(idx)
                    st.rerun()
    
    # Step 2: Generate Files
    if st.session_state.intersections_data:
        st.markdown('<div class="step-header"><h2>Step 2: Generate Synchro Files</h2></div>', unsafe_allow_html=True)
        
        if st.button("🚀 Generate Synchro Network", type="primary", use_container_width=True):
            if not user_email:
                st.error("Please enter your email in the sidebar!")
            else:
                with st.spinner("Generating network..."):
                    generator = SynchroGenerator()
                    file_content = generator.generate_network(st.session_state.intersections_data)
                    
                    # Save to Google Drive
                    file_link = save_to_google_drive("synchro_network.txt", file_content, user_email)
                    
                    # Log to Google Sheets
                    intersection_names = [int_data['name'] for int_data in st.session_state.intersections_data]
                    log_to_google_sheets(user_email, intersection_names, file_link, "Success")
                    
                    # Display success
                    st.markdown('<div class="success-box">', unsafe_allow_html=True)
                    st.success("✅ Synchro network generated successfully!")
                    if file_link:
                        st.info(f"📁 Backup saved to Google Drive: [View File]({file_link})")
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Download buttons
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.download_button(
                            label="📥 Download .txt file",
                            data=file_content,
                            file_name="synchro_network.txt",
                            mime="text/plain",
                            use_container_width=True
                        )
                    
                    with col2:
                        # CSV version (replace tabs with commas)
                        csv_content = file_content.replace('\t', ',')
                        st.download_button(
                            label="📥 Download .csv file",
                            data=csv_content,
                            file_name="synchro_network.csv",
                            mime="text/csv",
                            use_container_width=True
                        )

if __name__ == "__main__":
    main()