import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
import plotly.express as px

# Konfiguracja szerokości strony
st.set_page_config(layout="wide")

# Rozszerzone dane o urządzeniach sieciowych
network_devices = {
    'Poland': [
        {'device': 'Router', 'ip': '192.168.1.1', 'status': 'Active', 'location': 'Warsaw', 'vendor': 'Cisco'},
        {'device': 'Switch', 'ip': '192.168.1.2', 'status': 'Active', 'location': 'Krakow', 'vendor': 'Arista'},
        {'device': 'Firewall', 'ip': '192.168.1.3', 'status': 'Inactive', 'location': 'Gdansk', 'vendor': 'CheckPoint'},
    ],
    'Germany': [
        {'device': 'Firewall', 'ip': '192.168.2.1', 'status': 'Active', 'location': 'Berlin', 'vendor': 'CheckPoint'},
        {'device': 'Router', 'ip': '192.168.2.2', 'status': 'Inactive', 'location': 'Munich', 'vendor': 'Cisco'},
        {'device': 'Switch', 'ip': '192.168.2.3', 'status': 'Active', 'location': 'Hamburg', 'vendor': 'Arista'},
    ],
    'France': [
        {'device': 'Switch', 'ip': '192.168.3.1', 'status': 'Active', 'location': 'Paris', 'vendor': 'Arista'},
        {'device': 'Router', 'ip': '192.168.3.2', 'status': 'Active', 'location': 'Lyon', 'vendor': 'Cisco'},
        {'device': 'Firewall', 'ip': '192.168.3.3', 'status': 'Active', 'location': 'Marseille', 'vendor': 'CheckPoint'},
    ]
}

# Stałe dla filtrów
DEVICE_TYPES = ['Router', 'Switch', 'Firewall']
VENDORS = ['Cisco', 'Arista', 'CheckPoint']

@st.cache_data
def load_europe_data():
    url = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
    world = gpd.read_file(url)
    european_countries = [
        'Poland', 'Germany', 'France', 'Spain', 'Italy', 'United Kingdom', 
        'Ireland', 'Portugal', 'Belgium', 'Netherlands', 'Switzerland', 
        'Austria', 'Czech Republic', 'Slovakia', 'Hungary', 'Slovenia', 
        'Croatia', 'Bosnia and Herzegovina', 'Serbia', 'Montenegro', 
        'Albania', 'North Macedonia', 'Greece', 'Bulgaria', 'Romania', 
        'Moldova', 'Ukraine', 'Belarus', 'Lithuania', 'Latvia', 'Estonia', 
        'Finland', 'Sweden', 'Norway', 'Denmark'
    ]
    europe = world[world['NAME'].isin(european_countries)]
    return europe

def filter_devices(devices, device_types, vendors):
    if not device_types and not vendors:  # Jeśli nic nie wybrano, pokaż wszystko
        return devices
    filtered = devices.copy()
    if device_types:
        filtered = [d for d in filtered if d['device'] in device_types]
    if vendors:
        filtered = [d for d in filtered if d['vendor'] in vendors]
    return filtered

def create_distribution_charts(devices):
    # Konwersja do DataFrame dla łatwiejszej analizy
    df = pd.DataFrame(devices)
    
    # Wykres rozkładu według typu urządzenia
    device_counts = df['device'].value_counts()
    device_fig = px.pie(
        values=device_counts.values,
        names=device_counts.index,
        title='Device Type Distribution',
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    device_fig.update_traces(textposition='inside', textinfo='percent+label')
    
    # Wykres rozkładu według vendora
    vendor_counts = df['vendor'].value_counts()
    vendor_fig = px.pie(
        values=vendor_counts.values,
        names=vendor_counts.index,
        title='Vendor Distribution',
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    vendor_fig.update_traces(textposition='inside', textinfo='percent+label')
    
    # Wykres status według typu urządzenia
    status_by_type = pd.crosstab(df['device'], df['status'])
    status_fig = px.bar(
        status_by_type,
        title='Device Status by Type',
        barmode='group',
        color_discrete_sequence=px.colors.qualitative.Set1
    )
    
    return device_fig, vendor_fig, status_fig

def create_map(europe, selected_country):
    m = folium.Map(location=[50.0, 10.0], zoom_start=4)
    
    def style_function(feature):
        country_name = feature['properties']['NAME']
        has_devices = country_name in network_devices
        
        if not has_devices:
            return {
                'fillColor': '#d3d3d3',
                'color': '#808080',
                'weight': 1,
                'fillOpacity': 0.1,
                'opacity': 0.3,
                'dashArray': '3'
            }
        elif country_name == selected_country:
            return {
                'fillColor': '#ffff00',
                'color': 'black',
                'weight': 2,
                'fillOpacity': 0.3,
                'opacity': 1,
                'dashArray': 'none'
            }
        else:
            return {
                'fillColor': '#90EE90',
                'color': 'black',
                'weight': 1,
                'fillOpacity': 0.2,
                'opacity': 1,
                'dashArray': 'none'
            }
    
    def highlight_function(feature):
        country_name = feature['properties']['NAME']
        if country_name in network_devices:
            return {
                'fillColor': '#0000ff',
                'color': 'black',
                'weight': 3,
                'fillOpacity': 0.3,
                'opacity': 1
            }
        return {
            'fillColor': '#d3d3d3',
            'color': '#808080',
            'weight': 1,
            'fillOpacity': 0.1,
            'opacity': 0.3
        }

    folium.GeoJson(
        europe.__geo_interface__,
        style_function=style_function,
        highlight_function=highlight_function,
        tooltip=folium.GeoJsonTooltip(
            fields=['NAME'],
            aliases=[''],
            style=('background-color: white; color: black; font-family: courier new; font-size: 12px; padding: 10px;'),
            sticky=True
        )
    ).add_to(m)
    
    return m

def main():
    st.title('Network Devices in Europe')
    
    # Inicjalizacja stanu sesji
    if 'selected_country' not in st.session_state:
        st.session_state.selected_country = 'Poland'
    if 'device_types' not in st.session_state:
        st.session_state.device_types = []
    if 'vendors' not in st.session_state:
        st.session_state.vendors = []
    
    # Wczytanie danych geograficznych Europy
    with st.spinner('Loading map data...'):
        europe = load_europe_data()
    
    # Kolumny na mapę i kontrolki - zmienione proporcje na 7:3
    col1, col2 = st.columns([7, 3])
    
    with col1:
        m = create_map(europe, st.session_state.selected_country)
        map_data = st_folium(
            m,
            height=500,  # Zwiększona wysokość mapy
            width=None,
            key="map"
        )
    
    with col2:
        # Wybór kraju
        available_countries = list(network_devices.keys())
        selected_country = st.selectbox(
            'Select country:', 
            available_countries,
            index=available_countries.index(st.session_state.selected_country),
            key="country_select"
        )
        
        # Filtry
        st.write("### Filters")
        
        # Device Type multi-select
        device_types = st.multiselect(
            'Device Types:',
            DEVICE_TYPES,
            default=st.session_state.device_types,
            key='device_type_select'
        )
        
        # Vendor multi-select
        vendors = st.multiselect(
            'Vendors:',
            VENDORS,
            default=st.session_state.vendors,
            key='vendor_select'
        )
        
        # Statystyki dla wybranego kraju
        if selected_country in network_devices:
            filtered_devices = filter_devices(
                network_devices[selected_country],
                device_types,
                vendors
            )
            total_devices = len(filtered_devices)
            active_devices = sum(1 for dev in filtered_devices if dev['status'] == 'Active')
            
            st.write("### Statistics")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Devices", total_devices)
            with col2:
                st.metric("Active Devices", active_devices)
        
        # Aktualizacja stanu
        if device_types != st.session_state.device_types:
            st.session_state.device_types = device_types
            st.rerun()
            
        if vendors != st.session_state.vendors:
            st.session_state.vendors = vendors
            st.rerun()
            
        if selected_country != st.session_state.selected_country:
            st.session_state.selected_country = selected_country
            st.rerun()
    
    # Obsługa kliknięcia na mapę
    if (map_data is not None and 
        map_data.get('last_active_drawing') is not None and 
        map_data['last_active_drawing'].get('properties') is not None):
        
        clicked_country = map_data['last_active_drawing']['properties'].get('NAME')
        
        if (clicked_country in network_devices and 
            clicked_country != st.session_state.selected_country):
            st.session_state.selected_country = clicked_country
            st.rerun()
    
    # Wyświetlenie wykresów i tabeli w trzech kolumnach
    if st.session_state.selected_country in network_devices:
        filtered_devices = filter_devices(
            network_devices[st.session_state.selected_country],
            device_types,
            vendors
        )
        
        if filtered_devices:
            # Wykresy w trzech kolumnach
            st.write("### Device Distribution")
            col1, col2, col3 = st.columns(3)
            
            device_fig, vendor_fig, status_fig = create_distribution_charts(filtered_devices)
            
            with col1:
                st.plotly_chart(device_fig, use_container_width=True)
            with col2:
                st.plotly_chart(vendor_fig, use_container_width=True)
            with col3:
                st.plotly_chart(status_fig, use_container_width=True)
            
            # Tabela
            st.write("### Device List")
            df = pd.DataFrame(filtered_devices)
            st.dataframe(
                df.style.apply(lambda x: ['background-color: #90EE90' if v == 'Active' else 'background-color: #FFB6C1' 
                                        for v in x], subset=['status']),
                hide_index=True,
                use_container_width=True  # Użycie pełnej szerokości kontenera
            )
        else:
            st.info("No devices match the selected filters.")

if __name__ == "__main__":
    main()