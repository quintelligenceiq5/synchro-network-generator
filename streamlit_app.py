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
    
    def generate_network(self, intersections_data, connections=None):
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
                    'center_node': center_id,
                    'intersection_idx': idx
                }
                all_nodes.append(approach_node)
                approaches.append(approach_node)
            
            # Store intersection data
            intersection = {
                'center_node': center_node,
                'approaches': approaches,
                'config': int_data,
                'idx': idx
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
        
        # Apply connections (merge approach nodes)
        if connections:
            for int1_idx, int2_idx in connections:
                self.connect_intersections(intersections, all_nodes, links, int1_idx, int2_idx)
        
        return self.generate_file_content(all_nodes, links, intersections)
    
    def connect_intersections(self, intersections, all_nodes, links, int1_idx, int2_idx):
        """Connect two intersections by merging their shared approach nodes"""
        int1 = next((i for i in intersections if i['idx'] == int1_idx), None)
        int2 = next((i for i in intersections if i['idx'] == int2_idx), None)
        
        if not int1 or not int2:
            return
        
        center1 = int1['center_node']
        center2 = int2['center_node']
        
        dx = center2['x'] - center1['x']
        dy = center2['y'] - center1['y']
        
        # Determine which approaches to merge based on relative positions
        if abs(dx) > abs(dy):  # East-West connection
            if dx > 0:  # int2 is east of int1
                dir1, dir2 = 'EB', 'WB'
            else:  # int2 is west of int1
                dir1, dir2 = 'WB', 'EB'
        else:  # North-South connection
            if dy > 0:  # int2 is north of int1
                dir1, dir2 = 'NB', 'SB'
            else:  # int2 is south of int1
                dir1, dir2 = 'SB', 'NB'
        
        # Find the approach nodes
        approach1 = next((a for a in int1['approaches'] if a['direction'] == dir1), None)
        approach2 = next((a for a in int2['approaches'] if a['direction'] == dir2), None)
        
        if not approach1 or not approach2:
            return
        
        # Calculate midpoint
        mid_x = (approach1['x'] + approach2['x']) // 2
        mid_y = (approach1['y'] + approach2['y']) // 2
        
        # Update approach1 position to midpoint
        approach1['x'] = mid_x
        approach1['y'] = mid_y
        
        # Update all links that reference approach2 to use approach1
        for link in links:
            if link['from_node'] == approach2['id']:
                link['from_node'] = approach1['id']
            if link['to_node'] == approach2['id']:
                link['to_node'] = approach1['id']
        
        # Remove approach2 from all_nodes
        all_nodes[:] = [n for n in all_nodes if n['id'] != approach2['id']]
        
        # Update distances in links
        dist1 = int(math.sqrt((mid_x - center1['x'])**2 + (mid_y - center1['y'])**2))
        dist2 = int(math.sqrt((mid_x - center2['x'])**2 + (mid_y - center2['y'])**2))
        
        for link in links:
            if link['from_node'] == approach1['id'] and link['to_node'] == center1['id']:
                link['distance'] = dist1
            elif link['from_node'] == center1['id'] and link['to_node'] == approach1['id']:
                link['distance'] = dist1
            elif link['from_node'] == approach1['id'] and link['to_node'] == center2['id']:
                link['distance'] = dist2
            elif link['from_node'] == center2['id'] and link['to_node'] == approach1['id']:
                link['distance'] = dist2
    
    def generate_lanes_section(self, center_node_id, intersections):
        """Generate complete lanes section for an intersection"""
        lanes_data = []
        
        # Find the intersection data
        intersection = next((i for i in intersections if i['center_node']['id'] == center_node_id), None)
        if not intersection:
            return lanes_data
        
        # For each direction, create lane data
        for direction in ['NB', 'SB', 'EB', 'WB']:
            # Find approach node for this direction
            approach = next((a for a in intersection['approaches'] if a['direction'] == direction), None)
            if not approach:
                continue
            
            # Determine destination nodes
            dest_nodes = {'L': None, 'T': None, 'R': None}
            
            # Through movement - opposite direction
            opposite_dir = {'NB': 'SB', 'SB': 'NB', 'EB': 'WB', 'WB': 'EB'}[direction]
            opposite_approach = next((a for a in intersection['approaches'] if a['direction'] == opposite_dir), None)
            if opposite_approach:
                dest_nodes['T'] = opposite_approach['id']
            
            # Left turn
            left_dir = {'NB': 'WB', 'SB': 'EB', 'EB': 'NB', 'WB': 'SB'}[direction]
            left_approach = next((a for a in intersection['approaches'] if a['direction'] == left_dir), None)
            if left_approach:
                dest_nodes['L'] = left_approach['id']
            
            # Right turn
            right_dir = {'NB': 'EB', 'SB': 'WB', 'EB': 'SB', 'WB': 'NB'}[direction]
            right_approach = next((a for a in intersection['approaches'] if a['direction'] == right_dir), None)
            if right_approach:
                dest_nodes['R'] = right_approach['id']
            
            lanes_data.append({
                'direction': direction,
                'approach_node': approach['id'],
                'dest_nodes': dest_nodes,
                'config': intersection['config']
            })
        
        return lanes_data
    
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
        
        # LANES SECTION - Complete version
        output.write("[Lanes]\t\t\t\t\t\t\t\t\n")
        output.write("Lane Group Data\t\t\t\t\t\t\t\t\n")
        output.write("RECORDNAME\tINTID\tNBL\tNBT\tNBR\tSBL\tSBT\tSBR\tEBL\tEBT\tEBR\tWBL\tWBT\tWBR\tPED\tHOLD\n")
        
        for intersection in intersections:
            center_id = intersection['center_node']['id']
            lanes_data = self.generate_lanes_section(center_id, intersections)
            
            if lanes_data:
                # Up Node row
                output.write(f"Up Node\t{center_id}\t")
                for d in ['NB', 'SB', 'EB', 'WB']:
                    ld = next((l for l in lanes_data if l['direction'] == d), None)
                    if ld:
                        output.write(f"{ld['approach_node']}\t{ld['approach_node']}\t{ld['approach_node']}\t")
                    else:
                        output.write("\t\t\t")
                output.write("\t\n")
                
                # Dest Node row
                output.write(f"Dest Node\t{center_id}\t")
                for d in ['NB', 'SB', 'EB', 'WB']:
                    ld = next((l for l in lanes_data if l['direction'] == d), None)
                    if ld:
                        output.write(f"{ld['dest_nodes']['L'] or ''}\t{ld['dest_nodes']['T'] or ''}\t{ld['dest_nodes']['R'] or ''}\t")
                    else:
                        output.write("\t\t\t")
                output.write("\t\n")
                
                # Lanes row
                output.write(f"Lanes\t{center_id}\t")
                for d in ['NB', 'SB', 'EB', 'WB']:
                    ld = next((l for l in lanes_data if l['direction'] == d), None)
                    if ld:
                        through_lanes = ld['config']['lanes'][d]
                        rt_shared = ld['config']['rt_shared'][d]
                        right_lanes = 0 if rt_shared == 2 else 1
                        output.write(f"1\t{through_lanes}\t{right_lanes}\t")
                    else:
                        output.write("\t\t\t")
                output.write("\t\n")
                
                # Shared row
                output.write(f"Shared\t{center_id}\t")
                for d in ['NB', 'SB', 'EB', 'WB']:
                    ld = next((l for l in lanes_data if l['direction'] == d), None)
                    if ld:
                        rt_shared = ld['config']['rt_shared'][d]
                        output.write(f"0\t{rt_shared}\t\t")
                    else:
                        output.write("\t\t\t")
                output.write("\t\n")
                
                # Width row
                output.write(f"Width\t{center_id}\t12\t12\t12\t12\t12\t12\t12\t12\t12\t12\t12\t12\t\t\n")
                
                # Storage row
                output.write(f"Storage\t{center_id}\t")
                for d in ['NB', 'SB', 'EB', 'WB']:
                    ld = next((l for l in lanes_data if l['direction'] == d), None)
                    if ld:
                        rt_storage = ld['config']['rt_storage'][d]
                        output.write(f"150\t\t{rt_storage}\t")
                    else:
                        output.write("\t\t\t")
                output.write("\t\n")
                
                # Additional rows
                output.write(f"Taper\t{center_id}\t25\t\t25\t25\t\t25\t25\t\t25\t25\t\t25\t\t\n")
                output.write(f"StLanes\t{center_id}\t1\t\t1\t1\t\t1\t1\t\t1\t1\t\t1\t\t\n")
                output.write(f"Grade\t{center_id}\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t\t\n")
                output.write(f"Speed\t{center_id}\t\t30\t\t\t30\t\t\t30\t\t\t30\t\t\t\n")
                output.write(f"Phase1\t{center_id}\t\t2\t\t\t6\t\t\t4\t\t\t8\t\t\t\n")
                output.write(f"PermPhase1\t{center_id}\t2\t\t2\t6\t\t6\t4\t\t4\t8\t\t8\t\t\n")
                output.write(f"LostTime\t{center_id}\t4\t4\t4\t4\t4\t4\t4\t4\t4\t4\t4\t4\t\t\n")
                output.write(f"Lost Time Adjust\t{center_id}\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t\t\n")
                output.write(f"IdealFlow\t{center_id}\t1900\t1900\t1900\t1900\t1900\t1900\t1900\t1900\t1900\t1900\t1900\t1900\t\t\n")
                output.write(f"SatFlow\t{center_id}\t1770\t3539\t1583\t1770\t3539\t1583\t1770\t3539\t1583\t1770\t3539\t1583\t\t\n")
                output.write(f"SatFlowPerm\t{center_id}\t1341\t3539\t1583\t1341\t3539\t1583\t1272\t3539\t1583\t1272\t3539\t1583\t\t\n")
                output.write(f"Allow RTOR\t{center_id}\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t\t\n")
                output.write(f"SatFlowRTOR\t{center_id}\t0\t0\t27\t0\t0\t27\t0\t0\t54\t0\t0\t54\t\t\n")
                output.write(f"Volume\t{center_id}\t25\t50\t25\t25\t50\t25\t50\t100\t50\t50\t100\t50\t\t\n")
                output.write(f"Peds\t{center_id}\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t\t\n")
                output.write(f"Bicycles\t{center_id}\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t\t\n")
                output.write(f"PHF\t{center_id}\t0.92\t0.92\t0.92\t0.92\t0.92\t0.92\t0.92\t0.92\t0.92\t0.92\t0.92\t0.92\t\t\n")
                output.write(f"Growth\t{center_id}\t100\t100\t100\t100\t100\t100\t100\t100\t100\t100\t100\t100\t\t\n")
                output.write(f"HeavyVehicles\t{center_id}\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t2\t\t\n")
                output.write(f"BusStops\t{center_id}\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t\t\n")
                output.write(f"Midblock\t{center_id}\t\t0\t\t\t0\t\t\t0\t\t\t0\t\t\t\n")
                output.write(f"Distance\t{center_id}\t\t{self.standard_approach_distance}\t\t\t{self.standard_approach_distance}\t\t\t{self.standard_approach_distance}\t\t\t{self.standard_approach_distance}\t\t\t\n")
                output.write(f"TravelTime\t{center_id}\t\t{self.standard_approach_distance/30*3600/5280:.1f}\t\t\t{self.standard_approach_distance/30*3600/5280:.1f}\t\t\t{self.standard_approach_distance/30*3600/5280:.1f}\t\t\t{self.standard_approach_distance/30*3600/5280:.1f}\t\t\t\n")
                output.write(f"Right Channeled\t{center_id}\t\t\t0\t\t\t0\t\t\t0\t\t\t0\t\t\n")
                output.write(f"Alignment\t{center_id}\t0\t0\t1\t0\t0\t1\t0\t0\t1\t0\t0\t1\t\t\n")
                output.write(f"Enter Blocked\t{center_id}\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t\t\n")
                output.write(f"HeadwayFact\t{center_id}\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t1\t\t\n")
                output.write(f"Turning Speed\t{center_id}\t15\t60\t9\t15\t60\t9\t15\t60\t9\t15\t60\t9\t\t\n")
                output.write(f"FirstDetect\t{center_id}\t20\t100\t20\t20\t100\t20\t20\t100\t20\t20\t100\t20\t\t\n")
                output.write(f"LastDetect\t{center_id}\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t\t\n")
                output.write(f"DetectPhase1\t{center_id}\t2\t2\t2\t6\t6\t6\t4\t4\t4\t8\t8\t8\t\t\n")
                output.write(f"DetectPhase2\t{center_id}\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t\t\n")
                output.write(f"DetectPhase3\t{center_id}\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t\t\n")
                output.write(f"DetectPhase4\t{center_id}\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t\t\n")
                output.write(f"SwitchPhase\t{center_id}\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t\t\n")
                output.write(f"numDetects\t{center_id}\t1\t2\t1\t1\t2\t1\t1\t2\t1\t1\t2\t1\t\t\n")
                output.write(f"DetectPos1\t{center_id}\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t\t\n")
                output.write(f"DetectSize1\t{center_id}\t20\t6\t20\t20\t6\t20\t20\t6\t20\t20\t6\t20\t\t\n")
                output.write(f"DetectType1\t{center_id}\t3\t3\t3\t3\t3\t3\t3\t3\t3\t3\t3\t3\t\t\n")
                output.write(f"DetectExtend1\t{center_id}\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t\t\n")
                output.write(f"DetectQueue1\t{center_id}\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t\t\n")
                output.write(f"DetectDelay1\t{center_id}\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t\t\n")
                output.write(f"DetectPos2\t{center_id}\t\t94\t\t\t94\t\t\t94\t\t\t94\t\t\t\n")
                output.write(f"DetectSize2\t{center_id}\t\t6\t\t\t6\t\t\t6\t\t\t6\t\t\t\n")
                output.write(f"DetectType2\t{center_id}\t\t3\t\t\t3\t\t\t3\t\t\t3\t\t\t\n")
                output.write(f"DetectExtend2\t{center_id}\t\t0\t\t\t0\t\t\t0\t\t\t0\t\t\t\n")
                output.write(f"Exit Lanes\t{center_id}\t\t0\t\t\t0\t\t\t0\t\t\t0\t\t\t\n")
                output.write(f"CBD\t{center_id}\t\t0\t\t\t\t\t\t\t\t\t\t\t\t\n")
                output.write(f"Lane Group Flow\t{center_id}\t27\t54\t27\t27\t54\t27\t54\t109\t54\t54\t109\t54\t\t\n")
        
        output.write("\t\t\t\t\t\t\t\t\n")
        
        # TIMEPLANS SECTION - Complete version
        output.write("[Timeplans]\t\t\t\t\t\t\t\t\n")
        output.write("Timing Plan Settings\t\t\t\t\t\t\t\t\n")
        output.write("RECORDNAME\tINTID\tDATA\t\t\t\t\t\t\n")
        
        for intersection in intersections:
            center_id = intersection['center_node']['id']
            output.write(f"Control Type\t{center_id}\t0\t\t\t\t\t\t\n")
            output.write(f"Cycle Length\t{center_id}\t40\t\t\t\t\t\t\n")
            output.write(f"Lock Timings\t{center_id}\t0\t\t\t\t\t\t\n")
            output.write(f"Referenced To\t{center_id}\t0\t\t\t\t\t\t\n")
            output.write(f"Reference Phase\t{center_id}\t2\t\t\t\t\t\t\n")
            output.write(f"Offset\t{center_id}\t8\t\t\t\t\t\t\n")
            output.write(f"Master\t{center_id}\t0\t\t\t\t\t\t\n")
            output.write(f"Yield\t{center_id}\t0\t\t\t\t\t\t\n")
            output.write(f"Node 0\t{center_id}\t{center_id}\t\t\t\t\t\t\n")
            output.write(f"Node 1\t{center_id}\t0\t\t\t\t\t\t\n")
        
        output.write("\t\t\t\t\t\t\t\t\n")
        
        # PHASES SECTION - Complete version
        output.write("[Phases]\t\t\t\t\t\t\t\t\n")
        output.write("Phasing Data\t\t\t\t\t\t\t\t\n")
        output.write("RECORDNAME\tINTID\tD1\tD2\tD3\tD4\tD5\tD6\tD7\tD8\t\t\t\t\n")
        
        for intersection in intersections:
            center_id = intersection['center_node']['id']
            output.write(f"BRP\t{center_id}\t111\t112\t211\t212\t121\t122\t221\t222\t\t\t\t\n")
            output.write(f"MinGreen\t{center_id}\t\t4\t\t4\t\t4\t\t4\t\t\t\t\n")
            output.write(f"MaxGreen\t{center_id}\t\t16\t\t16\t\t16\t\t16\t\t\t\t\n")
            output.write(f"VehExt\t{center_id}\t\t3\t\t3\t\t3\t\t3\t\t\t\t\n")
            output.write(f"TimeBeforeReduce\t{center_id}\t\t0\t\t0\t\t0\t\t0\t\t\t\t\n")
            output.write(f"TimeToReduce\t{center_id}\t\t0\t\t0\t\t0\t\t0\t\t\t\t\n")
            output.write(f"MinGap\t{center_id}\t\t3\t\t3\t\t3\t\t3\t\t\t\t\n")
            output.write(f"Yellow\t{center_id}\t\t3.5\t\t3.5\t\t3.5\t\t3.5\t\t\t\t\n")
            output.write(f"AllRed\t{center_id}\t\t0.5\t\t0.5\t\t0.5\t\t0.5\t\t\t\t\n")
            output.write(f"Recall\t{center_id}\t\t3\t\t3\t\t3\t\t3\t\t\t\t\n")
            output.write(f"Walk\t{center_id}\t\t5\t\t5\t\t5\t\t5\t\t\t\t\n")
            output.write(f"DontWalk\t{center_id}\t\t11\t\t11\t\t11\t\t11\t\t\t\t\n")
            output.write(f"PedCalls\t{center_id}\t\t0\t\t0\t\t0\t\t0\t\t\t\t\n")
            output.write(f"MinSplit\t{center_id}\t\t20\t\t20\t\t20\t\t20\t\t\t\t\n")
            output.write(f"DualEntry\t{center_id}\t\t1\t\t1\t\t1\t\t1\t\t\t\t\n")
            output.write(f"InhibitMax\t{center_id}\t\t1\t\t1\t\t1\t\t1\t\t\t\t\n")
            output.write(f"Start\t{center_id}\t\t8\t\t28\t\t8\t\t28\t\t\t\t\n")
            output.write(f"End\t{center_id}\t\t28\t\t8\t\t28\t\t8\t\t\t\t\n")
            output.write(f"Yield\t{center_id}\t\t24\t\t4\t\t24\t\t4\t\t\t\t\n")
            output.write(f"Yield170\t{center_id}\t\t13\t\t33\t\t13\t\t33\t\t\t\t\n")
            output.write(f"LocalStart\t{center_id}\t\t0\t\t20\t\t0\t\t20\t\t\t\t\n")
            output.write(f"LocalYield\t{center_id}\t\t16\t\t36\t\t16\t\t36\t\t\t\t\n")
            output.write(f"LocalYield170\t{center_id}\t\t5\t\t25\t\t5\t\t25\t\t\t\t\n")
            output.write(f"ActGreen\t{center_id}\t\t16\t\t16\t\t16\t\t16\t\t\t\t\n")
        
        output.write("\t\t\t\t\t\t\t\t\n")
        
        return output.getvalue()

def save_to_google_drive(filename, content, user_email):
    """Save file to Google Drive"""
    try:
        # Convert st.secrets to dict properly
        creds_dict = {
            "type": st.secrets["google_credentials"]["type"],
            "project_id": st.secrets["google_credentials"]["project_id"],
            "private_key_id": st.secrets["google_credentials"]["private_key_id"],
            "private_key": st.secrets["google_credentials"]["private_key"],
            "client_email": st.secrets["google_credentials"]["client_email"],
            "client_id": st.secrets["google_credentials"]["client_id"],
            "auth_uri": st.secrets["google_credentials"]["auth_uri"],
            "token_uri": st.secrets["google_credentials"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["google_credentials"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["google_credentials"]["client_x509_cert_url"],
            "universe_domain": st.secrets["google_credentials"]["universe_domain"]
        }
        
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        
        service = build('drive', 'v3', credentials=creds)
        
        folder_id = st.secrets["google_credentials"]["google_drive_folder_id"]
        
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
        # Convert st.secrets to dict properly
        creds_dict = {
            "type": st.secrets["google_credentials"]["type"],
            "project_id": st.secrets["google_credentials"]["project_id"],
            "private_key_id": st.secrets["google_credentials"]["private_key_id"],
            "private_key": st.secrets["google_credentials"]["private_key"],
            "client_email": st.secrets["google_credentials"]["client_email"],
            "client_id": st.secrets["google_credentials"]["client_id"],
            "auth_uri": st.secrets["google_credentials"]["auth_uri"],
            "token_uri": st.secrets["google_credentials"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["google_credentials"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["google_credentials"]["client_x509_cert_url"],
            "universe_domain": st.secrets["google_credentials"]["universe_domain"]
        }
        
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

    # TEMPORARY DEBUG CODE - Remove after fixing
    st.write("DEBUG: Available secrets keys:")
    st.write(list(st.secrets.keys()))
    if "google_credentials" in st.secrets:
        st.write("google_credentials keys:", list(st.secrets["google_credentials"].keys()))
    # END DEBUG CODE
       
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
    
    # Intersection name input (outside form)
    intersection_name = st.text_input(
        "Intersection Name:",
        placeholder="Haggerty Road and 10 Mile Road, Novi, Michigan",
        key="intersection_input"
    )
    
    if st.button("➕ Configure This Intersection", type="primary"):
        if intersection_name:
            st.session_state.configuring_intersection = intersection_name
        else:
            st.warning("Please enter an intersection name first!")
    
    # Configuration section (appears when user clicks configure)
    if 'configuring_intersection' in st.session_state and st.session_state.configuring_intersection:
        st.markdown("---")
        st.subheader(f"⚙️ Configuration for: {st.session_state.configuring_intersection}")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.write("**Northbound**")
            nb_lanes = st.number_input("Lanes", min_value=1, max_value=6, value=2, key="nb_lanes")
            nb_speed = st.number_input("Speed (mph)", min_value=15, max_value=70, value=30, key="nb_speed")
            nb_twltl = 1 if st.checkbox("TWLTL", key="nb_twltl") else 0
            nb_rt_shared = st.checkbox("Right turn shared", value=True, key="nb_rt_shared")
            nb_rt_storage = 150
            if not nb_rt_shared:
                nb_rt_storage = st.number_input("RT Storage (ft)", min_value=50, max_value=500, value=150, key="nb_rt_storage")
        
        with col2:
            st.write("**Southbound**")
            sb_lanes = st.number_input("Lanes", min_value=1, max_value=6, value=2, key="sb_lanes")
            sb_speed = st.number_input("Speed (mph)", min_value=15, max_value=70, value=30, key="sb_speed")
            sb_twltl = 1 if st.checkbox("TWLTL", key="sb_twltl") else 0
            sb_rt_shared = st.checkbox("Right turn shared", value=True, key="sb_rt_shared")
            sb_rt_storage = 150
            if not sb_rt_shared:
                sb_rt_storage = st.number_input("RT Storage (ft)", min_value=50, max_value=500, value=150, key="sb_rt_storage")
        
        with col3:
            st.write("**Eastbound**")
            eb_lanes = st.number_input("Lanes", min_value=1, max_value=6, value=2, key="eb_lanes")
            eb_speed = st.number_input("Speed (mph)", min_value=15, max_value=70, value=30, key="eb_speed")
            eb_twltl = 1 if st.checkbox("TWLTL", key="eb_twltl") else 0
            eb_rt_shared = st.checkbox("Right turn shared", value=True, key="eb_rt_shared")
            eb_rt_storage = 150
            if not eb_rt_shared:
                eb_rt_storage = st.number_input("RT Storage (ft)", min_value=50, max_value=500, value=150, key="eb_rt_storage")
        
        with col4:
            st.write("**Westbound**")
            wb_lanes = st.number_input("Lanes", min_value=1, max_value=6, value=2, key="wb_lanes")
            wb_speed = st.number_input("Speed (mph)", min_value=15, max_value=70, value=30, key="wb_speed")
            wb_twltl = 1 if st.checkbox("TWLTL", key="wb_twltl") else 0
            wb_rt_shared = st.checkbox("Right turn shared", value=True, key="wb_rt_shared")
            wb_rt_storage = 150
            if not wb_rt_shared:
                wb_rt_storage = st.number_input("RT Storage (ft)", min_value=50, max_value=500, value=150, key="wb_rt_storage")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            if st.button("✅ Confirm & Add Intersection", type="primary", use_container_width=True):
                int_data = {
                    'name': st.session_state.configuring_intersection,
                    'lanes': {'NB': nb_lanes, 'SB': sb_lanes, 'EB': eb_lanes, 'WB': wb_lanes},
                    'speed': {'NB': nb_speed, 'SB': sb_speed, 'EB': eb_speed, 'WB': wb_speed},
                    'twltl': {'NB': nb_twltl, 'SB': sb_twltl, 'EB': eb_twltl, 'WB': wb_twltl},
                    'rt_shared': {
                        'NB': 2 if nb_rt_shared else 0,
                        'SB': 2 if sb_rt_shared else 0,
                        'EB': 2 if eb_rt_shared else 0,
                        'WB': 2 if wb_rt_shared else 0
                    },
                    'rt_storage': {
                        'NB': nb_rt_storage,
                        'SB': sb_rt_storage,
                        'EB': eb_rt_storage,
                        'WB': wb_rt_storage
                    }
                }
                st.session_state.intersections_data.append(int_data)
                st.success(f"✅ Added: {st.session_state.configuring_intersection}")
                del st.session_state.configuring_intersection
                st.rerun()
        
        with col_b:
            if st.button("❌ Cancel", use_container_width=True):
                del st.session_state.configuring_intersection
                st.rerun()
    
    # Display added intersections
    if st.session_state.intersections_data:
        st.markdown("### 📍 Added Intersections:")
        for idx, int_data in enumerate(st.session_state.intersections_data):
            with st.expander(f"{idx+1}. {int_data['name']}", expanded=False):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("NB Lanes", int_data['lanes']['NB'])
                col2.metric("SB Lanes", int_data['lanes']['SB'])
                col3.metric("EB Lanes", int_data['lanes']['EB'])
                col4.metric("WB Lanes", int_data['lanes']['WB'])
                
                if st.button(f"🗑️ Remove", key=f"remove_{idx}"):
                    st.session_state.intersections_data.pop(idx)
                    st.rerun()
    
    # Step 1.5: Connect Intersections (NEW FEATURE)
    if len(st.session_state.intersections_data) >= 2:
        st.markdown('<div class="step-header"><h2>Step 1.5: Connect Adjacent Intersections (Optional)</h2></div>', unsafe_allow_html=True)
        
        st.info("""
        **💡 Connect intersections to create corridors**
        
        When two intersections are connected:
        - Their shared approach nodes are merged
        - Creates a continuous roadway segment
        - Distances are automatically calculated
        
        **Example:** If Intersection A is east of Intersection B, connecting them merges:
        - Intersection A's WB approach with Intersection B's EB approach
        """)
        
        # Initialize connections list
        if 'connections' not in st.session_state:
            st.session_state.connections = []
        
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            int1_idx = st.selectbox(
                "First Intersection:",
                options=range(len(st.session_state.intersections_data)),
                format_func=lambda x: f"{x}: {st.session_state.intersections_data[x]['name']}",
                key="connect_int1"
            )
        
        with col2:
            int2_idx = st.selectbox(
                "Second Intersection:",
                options=range(len(st.session_state.intersections_data)),
                format_func=lambda x: f"{x}: {st.session_state.intersections_data[x]['name']}",
                key="connect_int2"
            )
        
        with col3:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button("🔗 Connect These", type="secondary"):
                if int1_idx == int2_idx:
                    st.error("Cannot connect an intersection to itself!")
                else:
                    # Check if already connected
                    connection = tuple(sorted([int1_idx, int2_idx]))
                    if connection in st.session_state.connections:
                        st.warning("These intersections are already connected!")
                    else:
                        st.session_state.connections.append(connection)
                        st.success(f"✅ Connected intersections {int1_idx} and {int2_idx}")
                        st.rerun()
        
        # Display connections
        if st.session_state.connections:
            st.markdown("#### 🔗 Active Connections:")
            for idx, (i1, i2) in enumerate(st.session_state.connections):
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.write(f"**{idx+1}.** {st.session_state.intersections_data[i1]['name']} ↔ {st.session_state.intersections_data[i2]['name']}")
                with col_b:
                    if st.button("❌ Remove", key=f"remove_conn_{idx}"):
                        st.session_state.connections.pop(idx)
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
                    
                    # Get connections if they exist
                    connections = st.session_state.get('connections', [])
                    
                    file_content = generator.generate_network(
                        st.session_state.intersections_data,
                        connections=connections
                    )
                    
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








