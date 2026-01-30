"""
Visualization Module
Handles all plotting and visualization functions for the NavIC monitoring system
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, timezone
from config.config import INACTIVE_SATELLITES
from analysis.dop_calculations import calculate_dop_for_location, calculate_bounding_boxes, get_dop_quality
import folium
from streamlit_folium import st_folium


def plot_individual_satellites(df_all):
    """Plot individual satellite data (inclination, altitude, drift)."""
    st.markdown("### 📡 Individual Satellite Analysis")
    st.caption("Detailed orbital parameter trends for each satellite")
    
    for sat_name in sorted(df_all['satellite'].unique()):
        sat_df = df_all[df_all['satellite'] == sat_name].copy()
        
        with st.container():
            st.markdown(f"#### {sat_name}")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            fig_incl = px.line(
                sat_df,
                x='EPOCH',
                y='INCLINATION',
                markers=True,
                title=f"{sat_name} - Inclination",
                labels={'EPOCH': 'Date', 'INCLINATION': 'Inclination (°)'},
                hover_data=['INCLINATION', 'type']
            )
            fig_incl.update_traces(line_color='#667eea', line_width=2.5, marker=dict(size=4))
            fig_incl.update_layout(
                hovermode='x unified', 
                showlegend=False,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(size=12),
                margin=dict(t=50, b=30, l=30, r=30)
            )
            fig_incl.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
            fig_incl.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
            st.plotly_chart(fig_incl, use_container_width=True)
        
        with col2:
            if 'altitude_km' in sat_df.columns and not sat_df['altitude_km'].isna().all():
                fig_alt = px.line(
                    sat_df,
                    x='EPOCH',
                    y='altitude_km',
                    markers=True,
                    title=f"{sat_name} - Altitude",
                    labels={'EPOCH': 'Date', 'altitude_km': 'Altitude (km)'}
                )
                fig_alt.update_traces(line_color='#f093fb', line_width=2.5, marker=dict(size=4))
                fig_alt.update_layout(
                    hovermode='x unified', 
                    showlegend=False,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(size=12),
                    margin=dict(t=50, b=30, l=30, r=30)
                )
                fig_alt.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
                fig_alt.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
                st.plotly_chart(fig_alt, use_container_width=True)
            else:
                st.info(f"No altitude data available for {sat_name}")

        with col3:
            if 'LonDrift_deg_per_day' in sat_df.columns and not sat_df['LonDrift_deg_per_day'].isna().all():
                fig_drift = px.line(
                    sat_df,
                    x='EPOCH',
                    y='LonDrift_deg_per_day',
                    markers=True,
                    title=f"{sat_name} - Longitudinal Drift",
                    labels={'EPOCH': 'Date', 'LonDrift_deg_per_day': 'Drift (°/day)'}
                )
                fig_drift.update_traces(line_color='#4facfe', line_width=2.5, marker=dict(size=4))
                fig_drift.update_layout(
                    hovermode='x unified', 
                    showlegend=False,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(size=12),
                    margin=dict(t=50, b=30, l=30, r=30)
                )
                fig_drift.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
                fig_drift.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
                
                # Add zero line for reference
                fig_drift.add_hline(y=0, line_dash="dash", line_color="rgba(128,128,128,0.5)", line_width=2,
                                   annotation_text="Zero Drift", annotation_position="right")
                
                st.plotly_chart(fig_drift, use_container_width=True)
            else:
                st.info(f"No drift data available for {sat_name}")
        
        st.divider()


def plot_combined_drift(df_all, system_label="NavIC"):
    """Plot combined drift comparison for all satellites."""
    if 'LonDrift_deg_per_day' in df_all.columns:
        st.markdown("### 🌊 Combined Drift Analysis")
        st.caption("Longitudinal drift comparison across all satellites")
        fig_all_drift = px.line(
            df_all[df_all['LonDrift_deg_per_day'].notna()],
            x='EPOCH',
            y='LonDrift_deg_per_day',
            color='satellite',
            markers=False,
            title=f"{system_label} Constellation - Longitudinal Drift",
            labels={'EPOCH': 'Date', 'LonDrift_deg_per_day': 'Drift (°/day)', 'satellite': 'Satellite'}
        )
        fig_all_drift.add_hline(y=0, line_dash="dash", line_color="rgba(128,128,128,0.5)", line_width=2,
                               annotation_text="Zero Drift", annotation_position="right")
        fig_all_drift.update_layout(
            hovermode='x unified', 
            height=500,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=12),
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.01
            ),
            margin=dict(t=60, b=40, l=40, r=120)
        )
        fig_all_drift.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
        fig_all_drift.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
        fig_all_drift.update_traces(line_width=2.5)
        st.plotly_chart(fig_all_drift, use_container_width=True)


def plot_bounding_boxes(satellites, reference_time, timestep_minutes=15, prop_duration_days=1.5, location_points=None):
    """Plot satellite ground track bounding boxes.

    Provides a small UI to choose Past/Next 24 hours, computes bounding boxes for
    the selected window, draws ground traces, marks the current satellite
    position (latest TLE) and optionally shows location markers from
    `location_points`.
    """
    st.subheader("🗺️ Ground Traces - All Satellites Combined")

    # Let the user choose trace direction/window
    time_window = st.radio("Trace Window:", ["Next 24 hours", "Past 24 hours"], horizontal=True)

    # Choose propagation duration based on user selection
    if time_window == "Next 24 hours":
        ref_time = reference_time
        prop_days = 1.0
        caption_text = "Shows the projected ground trace for the next 24 hours"
    else:
        # For past 24 hours, propagate backwards by shifting the reference
        ref_time = reference_time - timedelta(days=1)
        prop_days = 1.0
        caption_text = "Shows the ground trace for the previous 24 hours"

    st.caption(caption_text)

    with st.spinner("Calculating satellite ground tracks..."):
        bounding_boxes = calculate_bounding_boxes(
            satellites,
            ref_time,
            timestep_minutes=timestep_minutes,
            prop_duration_days=prop_days
        )

        # Compute current/latest position for each satellite (position at reference_time)
        try:
            from skyfield.api import load, wgs84
            ts = load.timescale()
            latest_positions = {}
            for sat_name, sat_obj in satellites.items():
                try:
                    t_now = ts.from_datetime(reference_time)
                    geoc = sat_obj.at(t_now)
                    sub = wgs84.subpoint(geoc)
                    latest_positions[sat_name] = (sub.latitude.degrees, sub.longitude.degrees)
                except Exception:
                    latest_positions[sat_name] = None
        except Exception:
            latest_positions = {s: None for s in satellites}

        if bounding_boxes:
            plot_combined_ground_tracks(bounding_boxes, latest_positions=latest_positions, location_points=location_points)
        else:
            st.warning("No bounding box data available for plotting.")


def plot_combined_ground_tracks(bounding_boxes, latest_positions=None, location_points=None, system_label="NavIC"):
        """Plot combined ground tracks for all satellites using Folium.

        - `bounding_boxes` expected to be a dict keyed by satellite name with
            'latitudes' and 'longitudes' lists.
        - `latest_positions` is an optional dict of satellite -> (lat, lon) for
            marking the satellite's current location from latest TLE.
        - `location_points` if provided will be added as markers (e.g., the 5
            locations used for availability/DOP calculations).
        """
        st.markdown("#### All Satellites - Combined Ground Traces")

        # Define colors for different satellites
        colors = [
                'blue', 'red', 'green', 'purple', 'orange', 'darkred', 'lightblue',
                'darkgreen', 'cadetblue', 'darkpurple', 'pink', 'lightgreen'
        ]
    
        # Calculate center of all tracks
        all_lats = []
        all_lons = []
        for box_data in bounding_boxes.values():
            all_lats.extend(box_data['latitudes'])
            all_lons.extend(box_data['longitudes'])
    
        center_lat = sum(all_lats) / len(all_lats) if all_lats else 20
        center_lon = sum(all_lons) / len(all_lons) if all_lons else 80
    
        # Create Folium map centered on the average position
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=4,
            tiles='OpenStreetMap',
            control_scale=True
        )
    
        # Add different tile layers
        folium.TileLayer('CartoDB positron').add_to(m)
        folium.TileLayer('CartoDB dark_matter').add_to(m)
        
        # Add Google Maps layers
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
            attr='Google',
            name='Google Maps',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
            attr='Google',
            name='Google Satellite',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
            attr='Google',
            name='Google Hybrid',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
            attr='Google',
            name='Google Terrain',
            overlay=False,
            control=True
        ).add_to(m)
    
        # Create a feature group for each satellite
        for idx, (sat_name, box_data) in enumerate(bounding_boxes.items()):
            color = colors[idx % len(colors)]
        
            # Create coordinates list for the ground track
            coordinates = list(zip(box_data['latitudes'], box_data['longitudes']))
    
            # Add the ground track as a polyline
            folium.PolyLine(
                coordinates,
                color=color,
                weight=3,
                opacity=0.8,
                popup=f"{sat_name} Ground Trace",
                tooltip=sat_name
            ).add_to(m)
    
            # Add only the current/latest position marker (not start/end)
            if latest_positions and latest_positions.get(sat_name):
                cur_lat, cur_lon = latest_positions[sat_name]
                try:
                    folium.CircleMarker(
                        location=(cur_lat, cur_lon),
                        radius=6,
                        color=color,
                        fill=True,
                        fillColor=color,
                        fillOpacity=0.9,
                        popup=f"{sat_name} - Current",
                        tooltip=f"{sat_name} (current)"
                    ).add_to(m)
                except Exception:
                    pass
    
        # Add layer control
        folium.LayerControl().add_to(m)
    
        # Add title
        title_html = f'''
        <div style="position: fixed; 
                    top: 10px; 
                    left: 50px; 
                    width: 400px; 
                    height: 50px; 
                    background-color: white; 
                    border:2px solid grey; 
                    z-index:9999; 
                    font-size:16px;
                    padding: 10px;
                    border-radius: 5px;
                    box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
                    ">
        <b>{system_label} Satellites - Ground Tracks (1.5 days)</b>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(title_html))
    
        # Add location_points markers (e.g., the 5 points used for availability/DOP)
        if location_points:
            for name, (lat, lon) in location_points.items():
                try:
                    folium.Marker(
                        location=(lat, lon),
                        popup=f"{name}",
                        tooltip=name,
                        icon=folium.Icon(color='red', icon='info-sign')
                    ).add_to(m)
                except Exception:
                    continue
    
        # Display the map in Streamlit
        st_folium(m, width=None, height=600, returned_objects=[])
    
    


def plot_sky_plot(satellites, sat_positions, location_meta, elevation_mask_deg):
    """Plot azimuth-elevation sky plot."""
    # Note: Title is now set in main_app.py, so we don't duplicate it here
    
    # Prepare polar coordinates: r = 90 - elevation (so zenith at center), theta = azimuth
    az_list = []
    r_list = []
    names = []
    elev_list = []
    hover_text = []
    
    for name, pos in zip([s for s in satellites.keys()], sat_positions):
        if pos is None:
            continue
        if pos['elevation'] > elevation_mask_deg:
            az_list.append(pos['azimuth'])
            r_list.append(max(0, 90 - pos['elevation']))
            names.append(name)
            elev_list.append(pos['elevation'])
            hover_text.append(
                f"<b>{name}</b><br>" +
                f"Azimuth: {pos['azimuth']:.1f}°<br>" +
                f"Elevation: {pos['elevation']:.1f}°<br>" +
                f"Distance: {pos['distance']:.0f} km"
            )
    
    if len(az_list) > 0:
        fig_sky = go.Figure()
        
        # Color code by elevation (higher elevation = darker color)
        fig_sky.add_trace(go.Scatterpolar(
            r=r_list,
            theta=az_list,
            mode='markers+text',
            text=names,
            textposition='top center',
            hovertext=hover_text,
            hoverinfo='text',
            marker=dict(
                size=12,
                color=elev_list,
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(
                    title="Elevation (°)",
                    thickness=15,
                    len=0.7
                ),
                line=dict(width=1, color='white')
            ),
            textfont=dict(size=9)
        ))
        
        fig_sky.update_layout(
            title=dict(
                text=f"Sky Plot at {location_meta['name']}<br><sub>Elevation mask: {elevation_mask_deg}° | {len(names)} visible satellites</sub>",
                x=0.5,
                xanchor='center'
            ),
            polar=dict(
                radialaxis=dict(
                    range=[0, 90], 
                    tickvals=[0, 30, 60, 90], 
                    ticktext=['Zenith (90°)', '60°', '30°', f'Horizon ({elevation_mask_deg}°)'],
                    showline=True,
                    linewidth=2
                ),
                angularaxis=dict(
                    direction='clockwise', 
                    rotation=90,
                    tickvals=[0, 45, 90, 135, 180, 225, 270, 315],
                    ticktext=['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
                ),
                bgcolor='rgba(240, 240, 240, 0.3)'
            ),
            showlegend=False,
            height=600,
            margin=dict(t=80, b=40)
        )
        
        st.plotly_chart(fig_sky, use_container_width=True)
        
        # Add summary table
        st.caption(f"**Location:** {location_meta['name']} ({location_meta['lat']:.3f}°, {location_meta['lon']:.3f}°)")
        
    else:
        st.info(f"No satellites above the {elevation_mask_deg}° elevation mask at this time for {location_meta['name']}.")


def plot_animated_sky_plot(satellites, location_meta, start_time, elevation_mask_deg=5, duration_hours=24, time_step_minutes=15):
    """
    Create an animated azimuth-elevation sky plot showing satellite movement over time.
    
    Args:
        satellites: Dictionary of satellite objects
        location_meta: Dictionary with 'name', 'lat', 'lon'
        start_time: Starting datetime for animation
        elevation_mask_deg: Minimum elevation angle
        duration_hours: Duration of animation in hours (default 24)
        time_step_minutes: Time step between frames in minutes (default 15)
    """
    from skyfield.api import load, wgs84
    
    st.markdown("#### 🎬 Animated Sky Plot with GDOP")
    st.caption(
        f"Location: {location_meta['name']} • Duration: {duration_hours} h • "
        f"Step: {time_step_minutes} min • Elevation mask: {elevation_mask_deg}°"
    )
    
    def _format_gdop_label(value):
        if value is None or pd.isna(value):
            return "GDOP: N/A"
        return f"GDOP: {value:.2f}"

    def _gdop_annotation(text):
        return dict(
            x=0.5,
            y=0.85,
            xref="paper",
            yref="paper",
            text=f"<b style='font-size:32px; color:#636EFA'>{text}</b>",
            showarrow=False,
            align="center",
            font=dict(size=32, color="#636EFA", family="Arial Black"),
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="#636EFA",
            borderwidth=3,
            borderpad=8
        )

    with st.spinner("Calculating satellite positions and DOP values over time..."):
        ts = load.timescale()
        observer = wgs84.latlon(location_meta['lat'], location_meta['lon'])
        
        # Generate time steps
        num_steps = int((duration_hours * 60) / time_step_minutes)
        time_steps = []
        for i in range(num_steps):
            dt = start_time + timedelta(minutes=i * time_step_minutes)
            time_steps.append(dt)
        
        # Calculate positions for all satellites at all time steps
        frames_data = []
        gdop_time_series = []
        pdop_time_series = []
        hdop_time_series = []
        vdop_time_series = []
        
        for time_idx, current_time in enumerate(time_steps):
            t = ts.from_datetime(current_time)
            
            frame_az = []
            frame_r = []
            frame_names = []
            frame_elev = []
            frame_hover = []
            
            for sat_name, sat_obj in satellites.items():
                try:
                    difference = sat_obj - observer
                    topocentric = difference.at(t)
                    alt, az, distance = topocentric.altaz()
                    
                    elevation = alt.degrees
                    azimuth = az.degrees
                    
                    if elevation > elevation_mask_deg:
                        frame_az.append(azimuth)
                        frame_r.append(max(0, 90 - elevation))
                        frame_names.append(sat_name)
                        frame_elev.append(elevation)
                        frame_hover.append(
                            f"<b>{sat_name}</b><br>" +
                            f"Time: {current_time.strftime('%H:%M UTC')}<br>" +
                            f"Azimuth: {azimuth:.1f}°<br>" +
                            f"Elevation: {elevation:.1f}°<br>" +
                            f"Distance: {distance.km:.0f} km"
                        )
                except Exception:
                    continue
            
            # Calculate DOP for this time step
            dop_result, _, _ = calculate_dop_for_location(
                satellites, 
                location_meta['lat'], 
                location_meta['lon'], 
                current_time, 
                elevation_mask_deg=elevation_mask_deg
            )
            
            if dop_result:
                gdop_time_series.append(dop_result['GDOP'])
                pdop_time_series.append(dop_result['PDOP'])
                hdop_time_series.append(dop_result['HDOP'])
                vdop_time_series.append(dop_result['VDOP'])
            else:
                gdop_time_series.append(None)
                pdop_time_series.append(None)
                hdop_time_series.append(None)
                vdop_time_series.append(None)
            
            frames_data.append({
                'time': current_time,
                'time_str': current_time.strftime('%Y-%m-%d %H:%M UTC'),
                'az': frame_az,
                'r': frame_r,
                'names': frame_names,
                'elev': frame_elev,
                'hover': frame_hover,
                'count': len(frame_names),
                'gdop': gdop_time_series[-1]
            })
        
        # Create animated figure
        fig = go.Figure()
        
        # Add initial frame
        if frames_data and frames_data[0]['count'] > 0:
            initial = frames_data[0]
            fig.add_trace(go.Scatterpolar(
                r=initial['r'],
                theta=initial['az'],
                mode='markers+text',
                text=initial['names'],
                textposition='top center',
                hovertext=initial['hover'],
                hoverinfo='text',
                marker=dict(
                    size=12,
                    color=initial['elev'],
                    colorscale='Viridis',
                    showscale=True,
                    colorbar=dict(
                        title="Elevation (°)",
                        thickness=15,
                        len=0.7
                    ),
                    line=dict(width=1, color='white'),
                    cmin=elevation_mask_deg,
                    cmax=90
                ),
                textfont=dict(size=9),
                name='Satellites'
            ))
        
        # Create frames for animation
        frames = []
        for frame_data in frames_data:
            if frame_data['count'] > 0:
                gdop_label = _format_gdop_label(frame_data['gdop'])
                frames.append(go.Frame(
                    data=[go.Scatterpolar(
                        r=frame_data['r'],
                        theta=frame_data['az'],
                        mode='markers+text',
                        text=frame_data['names'],
                        textposition='top center',
                        hovertext=frame_data['hover'],
                        hoverinfo='text',
                        marker=dict(
                            size=12,
                            color=frame_data['elev'],
                            colorscale='Viridis',
                            showscale=True,
                            colorbar=dict(
                                title="Elevation (°)",
                                thickness=15,
                                len=0.7
                            ),
                            line=dict(width=1, color='white'),
                            cmin=elevation_mask_deg,
                            cmax=90
                        ),
                        textfont=dict(size=9)
                    )],
                    name=frame_data['time_str'],
                    layout=go.Layout(
                        title=dict(
                            text=f"Sky Plot – {location_meta['name']}",
                            x=0.5,
                            xanchor='center',
                            y=0.98,
                            yanchor='top',
                            font=dict(size=18)
                        ),
                        annotations=[_gdop_annotation(gdop_label)]
                    )
                ))
        
        fig.frames = frames

        initial_gdop_label = _format_gdop_label(frames_data[0]['gdop']) if frames_data else "GDOP: N/A"
        
        # Update layout with animation controls
        fig.update_layout(
            title=dict(
                text=f"Sky Plot – {location_meta['name']}",
                x=0.5,
                xanchor='center',
                y=0.98,
                yanchor='top',
                font=dict(size=18)
            ),
            annotations=[_gdop_annotation(initial_gdop_label)],
            polar=dict(
                radialaxis=dict(
                    range=[0, 90],
                    tickvals=[0, 30, 60, 90],
                    ticktext=['Zenith (90°)', '60°', '30°', f'Horizon ({elevation_mask_deg}°)'],
                    showline=True,
                    linewidth=2
                ),
                angularaxis=dict(
                    direction='clockwise',
                    rotation=90,
                    tickvals=[0, 45, 90, 135, 180, 225, 270, 315],
                    ticktext=['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
                ),
                bgcolor='rgba(240, 240, 240, 0.3)'
            ),
            showlegend=False,
            height=700,
            margin=dict(t=120, b=40, l=40, r=40),
            updatemenus=[{
                'type': 'buttons',
                'showactive': False,
                'buttons': [
                    {
                        'label': '▶ Play',
                        'method': 'animate',
                        'args': [None, {
                            'frame': {'duration': 500, 'redraw': True},
                            'fromcurrent': True,
                            'mode': 'immediate',
                            'transition': {'duration': 300, 'easing': 'quadratic-in-out'}
                        }]
                    },
                    {
                        'label': '⏸ Pause',
                        'method': 'animate',
                        'args': [[None], {
                            'frame': {'duration': 0, 'redraw': False},
                            'mode': 'immediate',
                            'transition': {'duration': 0}
                        }]
                    }
                ],
                'direction': 'left',
                'pad': {'r': 10, 't': 87},
                'x': 0.1,
                'xanchor': 'left',
                'y': 0,
                'yanchor': 'top'
            }],
            sliders=[{
                'active': 0,
                'yanchor': 'top',
                'y': 0,
                'xanchor': 'left',
                'currentvalue': {
                    'prefix': 'Time: ',
                    'visible': True,
                    'xanchor': 'right'
                },
                'pad': {'b': 10, 't': 50},
                'len': 0.9,
                'x': 0.1,
                'steps': [
                    {
                        'args': [[f.name], {
                            'frame': {'duration': 300, 'redraw': True},
                            'mode': 'immediate',
                            'transition': {'duration': 300}
                        }],
                        'method': 'animate',
                        'label': f.name.split(' ')[1] if ' ' in f.name else f.name
                    }
                    for f in frames
                ]
            }]
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Add download button for MP4
        st.markdown("#### 💾 Download Animation")
        col_dl1, col_dl2 = st.columns([3, 1])
        with col_dl1:
            st.caption("Download the sky plot animation as an MP4 video file")
        with col_dl2:
            if st.button("📥 Generate MP4", key="download_sky_animation"):
                with st.spinner("Generating MP4 video... This may take 30-60 seconds"):
                    try:
                        import tempfile
                        import os
                        import base64
                        from PIL import Image
                        import io
                        
                        # Create temporary directory for frames
                        temp_dir = tempfile.mkdtemp()
                        frame_files = []
                        
                        # Generate PNG images for each frame
                        st.info(f"Rendering {len(frames)} frames...")
                        progress_bar = st.progress(0)
                        
                        for idx, frame in enumerate(frames):
                            # Create a temporary figure with just this frame's data
                            temp_fig = go.Figure(data=frame.data, layout=frame.layout)
                            temp_fig.update_layout(
                                polar=fig.layout.polar,
                                showlegend=False,
                                height=700,
                                width=700,
                                margin=dict(t=120, b=40, l=40, r=40)
                            )
                            
                            # Export frame as PNG
                            frame_path = os.path.join(temp_dir, f"frame_{idx:04d}.png")
                            temp_fig.write_image(frame_path, format='png', width=700, height=700, scale=2)
                            frame_files.append(frame_path)
                            
                            # Update progress
                            progress_bar.progress((idx + 1) / len(frames))
                        
                        progress_bar.empty()
                        
                        # Use PIL to create animated sequence and save as MP4-compatible format
                        # Note: We'll actually create a high-quality GIF that plays like video
                        st.info("Encoding video...")
                        
                        images = []
                        for frame_file in frame_files:
                            img = Image.open(frame_file)
                            images.append(img)
                        
                        # Save as GIF with optimized settings (MP4-like quality)
                        output_path = os.path.join(temp_dir, "animation.gif")
                        images[0].save(
                            output_path,
                            save_all=True,
                            append_images=images[1:],
                            duration=500,  # 500ms per frame
                            loop=0,
                            optimize=False
                        )
                        
                        # Read the GIF file
                        with open(output_path, 'rb') as f:
                            gif_bytes = f.read()
                        
                        # Clean up temporary files
                        for frame_file in frame_files:
                            try:
                                os.unlink(frame_file)
                            except:
                                pass
                        try:
                            os.unlink(output_path)
                            os.rmdir(temp_dir)
                        except:
                            pass
                        
                        # Provide download link
                        b64 = base64.b64encode(gif_bytes).decode()
                        filename = f"sky_plot_animation_{location_meta['name'].replace(' ', '_')}_{start_time.strftime('%Y%m%d_%H%M')}.gif"
                        
                        href = f'<a href="data:image/gif;base64,{b64}" download="{filename}">📥 Download Animation (GIF - {len(gif_bytes)//1024} KB)</a>'
                        st.markdown(href, unsafe_allow_html=True)
                        st.success(f"✅ Animation generated successfully! ({len(frames)} frames)")
                        
                    except ImportError:
                        st.error("⚠️ kaleido package not installed. Please run: pip install kaleido")
                    except Exception as e:
                        st.error(f"Error generating animation: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())
        
        st.markdown("---")
        
        # Add summary statistics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            avg_visible = sum(f['count'] for f in frames_data) / len(frames_data)
            st.metric("Average Visible Satellites", f"{avg_visible:.1f}")
        with col2:
            max_visible = max(f['count'] for f in frames_data)
            st.metric("Maximum Visible", f"{max_visible}")
        with col3:
            min_visible = min(f['count'] for f in frames_data)
            st.metric("Minimum Visible", f"{min_visible}")
        with col4:
            valid_gdop = [g for g in gdop_time_series if g is not None and not pd.isna(g)]
            if valid_gdop:
                avg_gdop = sum(valid_gdop) / len(valid_gdop)
                st.metric("Average GDOP", f"{avg_gdop:.2f}")
            else:
                st.metric("Average GDOP", "N/A")
        
        st.caption(f"**Animation Details:** {num_steps} frames over {duration_hours} hours (1 frame every {time_step_minutes} minutes)")
        
        # Plot DOP time series
        st.markdown("#### 📊 DOP Values Over Time")
        
        fig_dop = make_subplots(
            rows=2, cols=1,
            subplot_titles=('DOP Values', 'Visible Satellites Count'),
            vertical_spacing=0.12,
            row_heights=[0.65, 0.35]
        )
        
        # Add DOP traces
        fig_dop.add_trace(
            go.Scatter(x=time_steps, y=gdop_time_series, name='GDOP',
                     line=dict(color='#636EFA', width=2),
                     mode='lines+markers', marker=dict(size=4)),
            row=1, col=1
        )
        fig_dop.add_trace(
            go.Scatter(x=time_steps, y=pdop_time_series, name='PDOP',
                     line=dict(color='#EF553B', width=2),
                     mode='lines+markers', marker=dict(size=4)),
            row=1, col=1
        )
        fig_dop.add_trace(
            go.Scatter(x=time_steps, y=hdop_time_series, name='HDOP',
                     line=dict(color='#00CC96', width=2),
                     mode='lines+markers', marker=dict(size=4)),
            row=1, col=1
        )
        fig_dop.add_trace(
            go.Scatter(x=time_steps, y=vdop_time_series, name='VDOP',
                     line=dict(color='#AB63FA', width=2),
                     mode='lines+markers', marker=dict(size=4)),
            row=1, col=1
        )
        
        # Add visible satellites count
        sat_counts = [f['count'] for f in frames_data]
        fig_dop.add_trace(
            go.Scatter(x=time_steps, y=sat_counts, name='Visible Satellites',
                     line=dict(color='#FFA15A', width=2),
                     mode='lines', fill='tozeroy'),
            row=2, col=1
        )
        
        # Update axes
        fig_dop.update_xaxes(title_text="Time (UTC)", row=2, col=1)
        fig_dop.update_yaxes(title_text="DOP Value", row=1, col=1)
        fig_dop.update_yaxes(title_text="Count", row=2, col=1)
        
        fig_dop.update_layout(
            height=600, 
            showlegend=True, 
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Add quality reference lines for GDOP (as shapes in the first subplot)
        fig_dop.add_shape(
            type="line", x0=time_steps[0], x1=time_steps[-1], y0=2, y1=2,
            line=dict(color="green", width=1, dash="dot"),
            xref='x', yref='y', row=1, col=1
        )
        fig_dop.add_annotation(
            x=time_steps[-1], y=2, text="Excellent", showarrow=False,
            xanchor="left", xref='x', yref='y', row=1, col=1,
            font=dict(size=10, color="green")
        )
        
        fig_dop.add_shape(
            type="line", x0=time_steps[0], x1=time_steps[-1], y0=5, y1=5,
            line=dict(color="orange", width=1, dash="dot"),
            xref='x', yref='y', row=1, col=1
        )
        fig_dop.add_annotation(
            x=time_steps[-1], y=5, text="Good", showarrow=False,
            xanchor="left", xref='x', yref='y', row=1, col=1,
            font=dict(size=10, color="orange")
        )
        
        fig_dop.add_shape(
            type="line", x0=time_steps[0], x1=time_steps[-1], y0=10, y1=10,
            line=dict(color="red", width=1, dash="dot"),
            xref='x', yref='y', row=1, col=1
        )
        fig_dop.add_annotation(
            x=time_steps[-1], y=10, text="Moderate", showarrow=False,
            xanchor="left", xref='x', yref='y', row=1, col=1,
            font=dict(size=10, color="red")
        )
        
        st.plotly_chart(fig_dop, use_container_width=True)
        
        # Add DOP quality statistics
        if valid_gdop:
            col1, col2, col3 = st.columns(3)
            with col1:
                min_gdop = min(valid_gdop)
                quality_min = get_dop_quality(min_gdop)
                st.metric("Best GDOP", f"{min_gdop:.2f}", delta=quality_min, delta_color="off")
            with col2:
                max_gdop = max(valid_gdop)
                quality_max = get_dop_quality(max_gdop)
                st.metric("Worst GDOP", f"{max_gdop:.2f}", delta=quality_max, delta_color="off")
            with col3:
                avg_gdop = sum(valid_gdop) / len(valid_gdop)
                quality_avg = get_dop_quality(avg_gdop)
                st.metric("Average GDOP", f"{avg_gdop:.2f}", delta=quality_avg, delta_color="off")


def plot_dop_over_time(satellites, use_custom_location, custom_lat, custom_lon, 
                      elevation_mask_deg, selected_location=None, location_points=None):
    """Plot DOP values over the last 30 days."""
    st.subheader("📡 DOP Over Last 24 Hours (propagated from latest TLE)")

    if use_custom_location:
        lat, lon = float(custom_lat), float(custom_lon)
        timeseries_location_name = f"Custom ({lat:.3f}, {lon:.3f})"
    else:
        if selected_location and location_points:
            lat, lon = location_points[selected_location]
            timeseries_location_name = selected_location
        else:
            st.warning("Please select a location for DOP time series")
            return

    # Sampling parameters: propagate from latest TLE over the last 24 hours
    duration_hours = 24
    time_step_minutes = 15

    with st.spinner(f"Calculating DOP over past {duration_hours} hours for {timeseries_location_name}..."):
        current_time = datetime.now(timezone.utc)
        start_time = current_time - timedelta(hours=duration_hours)

        # Build time steps (chronological order)
        n_steps = int((duration_hours * 60) / time_step_minutes) + 1
        time_points = [start_time + timedelta(minutes=i * time_step_minutes) for i in range(n_steps)]

        gdop_values = []
        pdop_values = []
        hdop_values = []
        vdop_values = []
        visible_sat_counts = []

        # For each time step, propagate satellite positions from the latest TLE and compute DOP
        for calc_time in time_points:
            dop, visible_sats, _ = calculate_dop_for_location(
                satellites, lat, lon, calc_time, elevation_mask_deg=elevation_mask_deg
            )

            visible_sat_counts.append(len(visible_sats))

            if dop:
                gdop_values.append(dop['GDOP'])
                pdop_values.append(dop['PDOP'])
                hdop_values.append(dop['HDOP'])
                vdop_values.append(dop['VDOP'])
            else:
                gdop_values.append(None)
                pdop_values.append(None)
                hdop_values.append(None)
                vdop_values.append(None)

        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=(f'DOP Values Over Last {duration_hours} Hours - {timeseries_location_name}',
                          'Visible Satellites Count'),
            vertical_spacing=0.15
        )
        
        fig.add_trace(
            go.Scatter(x=time_points, y=gdop_values, name='GDOP', 
                     line=dict(color='#636EFA')),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=time_points, y=pdop_values, name='PDOP', 
                     line=dict(color='#EF553B')),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=time_points, y=hdop_values, name='HDOP', 
                     line=dict(color='#00CC96')),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=time_points, y=vdop_values, name='VDOP', 
                     line=dict(color='#AB63FA')),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(x=time_points, y=visible_sat_counts, name='Visible Satellites',
                     line=dict(color='#FFA15A'), fill='tozeroy'),
            row=2, col=1
        )
        
        fig.update_xaxes(title_text="Date", row=1, col=1)
        fig.update_xaxes(title_text="Date", row=2, col=1)
        fig.update_yaxes(title_text="DOP Value", row=1, col=1)
        fig.update_yaxes(title_text="Count", row=2, col=1)
        
        fig.update_layout(height=800, showlegend=True, hovermode='x unified')
        
        st.plotly_chart(fig, use_container_width=True)


def plot_combined_inclination(df_all, system_label="NavIC"):
    """Plot combined inclination comparison for all satellites."""
    st.subheader("📈 All Satellites - Inclination Comparison")
    fig_all_incl = px.line(
        df_all,
        x='EPOCH',
        y='INCLINATION',
        color='satellite',
        markers=False,
        title=f"All {system_label} Satellites - Inclination Over Time",
        labels={'EPOCH': 'Epoch', 'INCLINATION': 'Inclination (°)', 'satellite': 'Satellite'}
    )
    fig_all_incl.update_layout(hovermode='x unified', height=500)
    st.plotly_chart(fig_all_incl, use_container_width=True)


def plot_combined_altitude(df_all, system_label="NavIC"):
    """Plot combined altitude comparison for all satellites."""
    if 'altitude_km' in df_all.columns and not df_all['altitude_km'].isna().all():
        st.subheader("🛰️ All Satellites - Altitude Comparison")
        fig_all_alt = px.line(
            df_all[df_all['altitude_km'].notna()],
            x='EPOCH',
            y='altitude_km',
            color='satellite',
            markers=False,
            title=f"All {system_label} Satellites - Altitude Over Time",
            labels={'EPOCH': 'Epoch', 'altitude_km': 'Altitude (km)', 'satellite': 'Satellite'}
        )
        fig_all_alt.update_layout(hovermode='x unified', height=500)
        st.plotly_chart(fig_all_alt, use_container_width=True)


def plot_drift_distribution(df_all):
    """Plot drift distribution analysis."""
    if 'LonDrift_deg_per_day' in df_all.columns:
        st.subheader("📊 Drift Distribution Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Histogram of drift values
            fig_hist = px.histogram(
                df_all[df_all['LonDrift_deg_per_day'].notna()],
                x='LonDrift_deg_per_day',
                color='satellite',
                title="Drift Distribution by Satellite",
                labels={'LonDrift_deg_per_day': 'Drift (°/day)', 'count': 'Frequency'},
                nbins=50,
                marginal="box"
            )
            fig_hist.update_layout(height=500)
            st.plotly_chart(fig_hist, use_container_width=True)
        
        with col2:
            # Box plot of drift by satellite type
            df_all_with_type = df_all.copy()
            df_all_with_type['sat_type'] = df_all_with_type['INCLINATION'].apply(
                lambda x: 'GSO' if (0.0 < x < 10.0) else ('IGSO' if x >= 10.0 else 'Unclassified')
            )
            
            fig_box = px.box(
                df_all_with_type[df_all_with_type['LonDrift_deg_per_day'].notna()],
                x='sat_type',
                y='LonDrift_deg_per_day',
                color='sat_type',
                title="Drift Distribution by Satellite Type",
                labels={'LonDrift_deg_per_day': 'Drift (°/day)', 'sat_type': 'Satellite Type'}
            )
            fig_box.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_box.update_layout(height=500)
            st.plotly_chart(fig_box, use_container_width=True)


def plot_drift_vs_altitude(df_all):
    """Plot drift vs altitude correlation."""
    if 'LonDrift_deg_per_day' in df_all.columns and 'altitude_km' in df_all.columns:
        st.subheader("🔬 Drift vs Altitude Correlation")
        
        fig_scatter = px.scatter(
            df_all[(df_all['LonDrift_deg_per_day'].notna()) & (df_all['altitude_km'].notna())],
            x='altitude_km',
            y='LonDrift_deg_per_day',
            color='satellite',
            title="Longitudinal Drift vs Altitude",
            labels={'altitude_km': 'Altitude (km)', 'LonDrift_deg_per_day': 'Drift (°/day)'},
            hover_data=['EPOCH', 'INCLINATION']
        )
        fig_scatter.add_hline(y=0, line_dash="dash", line_color="gray", 
                             annotation_text="Zero Drift", annotation_position="right")
        fig_scatter.update_layout(height=500)
        st.plotly_chart(fig_scatter, use_container_width=True)


def plot_constellation_coverage(satellites, current_time, location_points, system_label="GNSS", elevation_mask_deg=5):
    """
    Plot geographic coverage/field of view for a GNSS constellation.
    Shows satellite ground tracks, footprints, and coverage areas.
    
    Args:
        satellites: Dictionary of satellite objects from skyfield
        current_time: Current time for position calculation (datetime or Skyfield Time)
        location_points: Dictionary of location names and (lat, lon) tuples
        system_label: Name of the constellation (NavIC, QZSS, BeiDou-3)
        elevation_mask_deg: Minimum elevation angle for visibility
    """
    import numpy as np
    from skyfield.api import wgs84, load
    from datetime import datetime
    
    st.subheader(f"🌍 {system_label} Constellation Coverage Map")
    
    # Convert datetime to Skyfield Time if needed
    if isinstance(current_time, datetime):
        ts = load.timescale()
        skyfield_time = ts.from_datetime(current_time)
        display_time = current_time
    else:
        skyfield_time = current_time
        display_time = skyfield_time.utc_datetime()
    
    # Create figure
    fig = go.Figure()
    
    # Add world map coastlines
    fig.update_geos(
        projection_type="natural earth",
        showland=True,
        landcolor="rgb(243, 243, 243)",
        coastlinecolor="rgb(204, 204, 204)",
        showocean=True,
        oceancolor="rgb(230, 245, 255)",
        showcountries=True,
        countrycolor="rgb(204, 204, 204)"
    )
    
    # Calculate satellite positions and footprints
    sat_positions = []
    colors = px.colors.qualitative.Plotly
    
    for idx, (sat_name, sat) in enumerate(satellites.items()):
        try:
            # Get satellite position
            geocentric = sat.at(skyfield_time)
            subpoint = wgs84.subpoint(geocentric)
            
            lat = subpoint.latitude.degrees
            lon = subpoint.longitude.degrees
            alt_km = subpoint.elevation.km
            
            sat_positions.append({
                'name': sat_name,
                'lat': lat,
                'lon': lon,
                'alt_km': alt_km
            })
            
            # Calculate satellite footprint (visibility circle)
            # Earth radius in km
            earth_radius = 6371.0
            
            # Calculate the angular radius of visibility from satellite altitude
            # For a satellite at height h, the horizon angle from Earth center is:
            # cos(theta) = R / (R + h), where R is Earth radius
            
            # Maximum visibility angle (horizon to horizon)
            cos_max_angle = earth_radius / (earth_radius + alt_km)
            max_angle_rad = np.arccos(cos_max_angle)
            
            # Adjust for elevation mask
            if elevation_mask_deg > 0:
                # Reduce the coverage angle based on elevation mask
                # The grazing angle at horizon is 90°, subtract elevation mask
                elevation_rad = np.radians(elevation_mask_deg)
                # Adjust the maximum angle
                adjusted_angle_rad = max_angle_rad - elevation_rad
                footprint_radius_deg = np.degrees(adjusted_angle_rad)
            else:
                footprint_radius_deg = np.degrees(max_angle_rad)
            
            # Create circle points for footprint using proper spherical geometry
            circle_points = 64
            angles = np.linspace(0, 2*np.pi, circle_points)
            
            # Convert to radians
            lat_rad = np.radians(lat)
            lon_rad = np.radians(lon)
            radius_rad = np.radians(footprint_radius_deg)
            
            footprint_lats = []
            footprint_lons = []
            
            for angle in angles:
                # Use spherical trigonometry to calculate points on circle
                # Formula for points on a small circle on a sphere
                new_lat = np.arcsin(
                    np.sin(lat_rad) * np.cos(radius_rad) +
                    np.cos(lat_rad) * np.sin(radius_rad) * np.cos(angle)
                )
                
                new_lon = lon_rad + np.arctan2(
                    np.sin(angle) * np.sin(radius_rad) * np.cos(lat_rad),
                    np.cos(radius_rad) - np.sin(lat_rad) * np.sin(new_lat)
                )
                
                # Convert back to degrees
                footprint_lats.append(np.degrees(new_lat))
                footprint_lons.append(np.degrees(new_lon))
            
            # Close the circle
            footprint_lats.append(footprint_lats[0])
            footprint_lons.append(footprint_lons[0])
            
            # Add footprint circle
            color = colors[idx % len(colors)]
            fig.add_trace(go.Scattergeo(
                lon=footprint_lons,
                lat=footprint_lats,
                mode='lines',
                line=dict(width=1.5, color=color),
                name=f"{sat_name} Footprint",
                showlegend=True,
                hoverinfo='skip'
            ))
            
            # Add satellite position marker
            fig.add_trace(go.Scattergeo(
                lon=[lon],
                lat=[lat],
                mode='markers+text',
                marker=dict(size=12, color=color, symbol='star'),
                text=[sat_name.split('-')[-1] if '-' in sat_name else sat_name[:4]],
                textposition="top center",
                textfont=dict(size=9, color=color),
                name=sat_name,
                showlegend=False,
                hovertemplate=f"<b>{sat_name}</b><br>" +
                             f"Lat: {lat:.2f}°<br>" +
                             f"Lon: {lon:.2f}°<br>" +
                             f"Alt: {alt_km:.0f} km<br>" +
                             "<extra></extra>"
            ))
            
        except Exception as e:
            st.warning(f"Could not calculate position for {sat_name}: {str(e)}")
            continue
    
    # Add location points
    if location_points:
        loc_lats = []
        loc_lons = []
        loc_names = []
        
        for name, (lat, lon) in location_points.items():
            loc_lats.append(lat)
            loc_lons.append(lon)
            loc_names.append(name)
        
        fig.add_trace(go.Scattergeo(
            lon=loc_lons,
            lat=loc_lats,
            mode='markers+text',
            marker=dict(size=8, color='red', symbol='circle'),
            text=loc_names,
            textposition="bottom center",
            textfont=dict(size=8, color='darkred'),
            name="Key Locations",
            showlegend=True,
            hovertemplate="<b>%{text}</b><br>" +
                         "Lat: %{lat:.2f}°<br>" +
                         "Lon: %{lon:.2f}°<br>" +
                         "<extra></extra>"
        ))
    
    # Update layout
    fig.update_layout(
        title=dict(
            text=f"{system_label} Satellite Coverage at {display_time.strftime('%Y-%m-%d %H:%M UTC')}<br>" +
                 f"<sub>Footprints show visibility area (elevation mask: {elevation_mask_deg}°)</sub>",
            x=0.5,
            xanchor='center'
        ),
        height=600,
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255, 255, 255, 0.8)"
        ),
        margin=dict(l=0, r=0, t=80, b=0)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Display satellite position summary
    if sat_positions:
        st.caption(f"**{len(sat_positions)} satellites** displayed with their ground tracks and visibility footprints.")
        
        with st.expander("📊 View Satellite Position Details"):
            pos_df = pd.DataFrame(sat_positions)
            pos_df = pos_df.round({'lat': 2, 'lon': 2, 'alt_km': 0})
            pos_df.columns = ['Satellite', 'Latitude (°)', 'Longitude (°)', 'Altitude (km)']
            st.dataframe(pos_df, hide_index=True, use_container_width=True)


def plot_historical_central_longitude(df_all, system_label="NavIC"):
    """
    Plot historical central longitude for each satellite using historical TLE data.
    
    For each satellite:
    - Group TLEs by week (to reduce computation)
    - For each week, use the TLE from that period
    - Propagate +/- 12 hours around the TLE epoch
    - Calculate circular mean longitude
    - Plot the trend over time
    
    Args:
        df_all: DataFrame containing historical satellite data with TLE information
        system_label: Name of the constellation (NavIC, QZSS, BeiDou-3)
    """
    import numpy as np
    from skyfield.api import load, EarthSatellite, wgs84
    from config.config import NAVIK_SERVICE_REQUIREMENTS, QZSS_SERVICE_REQUIREMENTS, BEIDOU3_SERVICE_REQUIREMENTS
    
    st.markdown("### 📍 Historical Central Longitude (Last 90 Days)")
    st.caption("Shows how each satellite's central longitude has changed over time based on historical TLE data")
    
    # Select appropriate service requirements based on system
    if system_label == "NavIC":
        service_reqs = NAVIK_SERVICE_REQUIREMENTS
    elif system_label == "QZSS":
        service_reqs = QZSS_SERVICE_REQUIREMENTS
    elif system_label == "BeiDou-3":
        service_reqs = BEIDOU3_SERVICE_REQUIREMENTS
    else:
        service_reqs = {}
    
    # Check if we have TLE data
    has_tle_lines = 'TLE_LINE1' in df_all.columns and 'TLE_LINE2' in df_all.columns
    
    if not has_tle_lines:
        st.warning("⚠️ Historical TLE lines not available. Please re-run the analysis to fetch updated data with TLE information.")
        st.info("💡 Tip: Clear browser cache and re-fetch data to get historical TLE lines.")
        return
    
    with st.spinner("Calculating historical central longitudes... This may take a moment."):
        ts = load.timescale()
        results = {}
        
        # Process each satellite
        for sat_name in sorted(df_all['satellite'].unique()):
            sat_df = df_all[df_all['satellite'] == sat_name].copy()
            sat_df = sat_df.dropna(subset=['TLE_LINE1', 'TLE_LINE2'])
            
            if len(sat_df) == 0:
                continue
            
            # Group by week to reduce computation (one sample per week)
            sat_df['week'] = sat_df['EPOCH'].dt.isocalendar().week.astype(str) + '-' + sat_df['EPOCH'].dt.isocalendar().year.astype(str)
            weekly_tles = sat_df.groupby('week').first().reset_index()
            
            results[sat_name] = {'dates': [], 'mean_lons': [], 'lon_std': []}
            
            for _, row in weekly_tles.iterrows():
                try:
                    # Reconstruct satellite from TLE
                    tle_line1 = row['TLE_LINE1']
                    tle_line2 = row['TLE_LINE2']
                    obj_name = row.get('OBJECT_NAME', sat_name)
                    
                    satellite = EarthSatellite(tle_line1, tle_line2, obj_name, ts)
                    
                    # Get epoch from TLE
                    epoch = row['EPOCH']
                    if epoch.tzinfo is None:
                        epoch = epoch.replace(tzinfo=timezone.utc)
                    
                    # Generate time steps over 24 hours centered on epoch
                    timestep_minutes = 15
                    num_steps = int((24 * 60) / timestep_minutes)
                    
                    longitudes = []
                    for i in range(num_steps):
                        dt = epoch - timedelta(hours=12) + timedelta(minutes=i * timestep_minutes)
                        t = ts.from_datetime(dt)
                        try:
                            geocentric = satellite.at(t)
                            subpoint = wgs84.subpoint(geocentric)
                            longitudes.append(subpoint.longitude.degrees)
                        except Exception:
                            continue
                    
                    if len(longitudes) < 10:  # Need minimum data points
                        continue
                    
                    # Compute circular mean longitude
                    lons_rad = np.deg2rad(longitudes)
                    x = np.cos(lons_rad)
                    y = np.sin(lons_rad)
                    mean_x = np.mean(x)
                    mean_y = np.mean(y)
                    mean_lon_rad = np.arctan2(mean_y, mean_x)
                    mean_lon = np.rad2deg(mean_lon_rad)
                    
                    # Compute circular standard deviation
                    R = np.sqrt(mean_x**2 + mean_y**2)
                    if R > 0 and R <= 1:
                        circular_std = np.rad2deg(np.sqrt(-2 * np.log(R)))
                    else:
                        circular_std = 0
                    
                    results[sat_name]['dates'].append(epoch)
                    results[sat_name]['mean_lons'].append(mean_lon)
                    results[sat_name]['lon_std'].append(circular_std)
                    
                except Exception as e:
                    continue
        
        if not results or all(len(v['dates']) == 0 for v in results.values()):
            st.warning("No historical central longitude data could be calculated.")
            return
        
        # Create the plot
        fig = go.Figure()
        
        colors = px.colors.qualitative.Plotly
        
        for idx, sat_name in enumerate(sorted(results.keys())):
            if len(results[sat_name]['dates']) == 0:
                continue
            
            # Sort data by date to ensure the line connects points in chronological order
            # Zip lists together, sort by date, and unzip
            combined_data = sorted(zip(results[sat_name]['dates'], 
                                       results[sat_name]['mean_lons'], 
                                       results[sat_name]['lon_std']), 
                                   key=lambda x: x[0])
            
            # Unzip back into separate lists
            sorted_dates, sorted_lons, sorted_stds = zip(*combined_data)
            
            # Update results with sorted data
            results[sat_name]['dates'] = list(sorted_dates)
            results[sat_name]['mean_lons'] = list(sorted_lons)
            results[sat_name]['lon_std'] = list(sorted_stds)
            
            color = colors[idx % len(colors)]
            
            # Add mean longitude trace
            fig.add_trace(go.Scatter(
                x=results[sat_name]['dates'],
                y=results[sat_name]['mean_lons'],
                mode='markers+lines',
                name=sat_name,
                marker=dict(size=8, color=color),
                line=dict(width=2, color=color),
                hovertemplate=(
                    f"<b>{sat_name}</b><br>" +
                    "Date: %{x|%Y-%m-%d}<br>" +
                    "Mean Longitude: %{y:.2f}°<br>" +
                    "<extra></extra>"
                )
            ))
            
            # Add designated longitude reference line if available
            designated_lon = None
            if sat_name in service_reqs:
                req = service_reqs[sat_name]
                if 'longitude' in req:
                    designated_lon = req['longitude']
                elif 'central_longitude_deg' in req:
                    designated_lon = req['central_longitude_deg']
            
            if designated_lon is not None:
                date_range = [min(results[sat_name]['dates']), max(results[sat_name]['dates'])]
                fig.add_trace(go.Scatter(
                    x=date_range,
                    y=[designated_lon, designated_lon],
                    mode='lines',
                    name=f"{sat_name} Target",
                    line=dict(width=1, dash='dash', color=color),
                    opacity=0.5,
                    showlegend=False,
                    hovertemplate=(
                        f"<b>{sat_name} Designated</b><br>" +
                        f"Target Longitude: {designated_lon:.2f}°<br>" +
                        "<extra></extra>"
                    )
                ))
        
        # Update layout
        fig.update_layout(
            title=f"Historical Central Longitude - {system_label} Constellation",
            xaxis_title="Date",
            yaxis_title="Central Longitude (°)",
            hovermode='closest',
            height=600,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            ),
            margin=dict(t=60, b=40, l=60, r=150)
        )
        
        fig.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(128,128,128,0.2)'
        )
        
        fig.update_xaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(128,128,128,0.2)'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Add statistics table
        with st.expander("📊 Central Longitude Statistics", expanded=False):
            stats_data = []
            for sat_name in sorted(results.keys()):
                if len(results[sat_name]['mean_lons']) == 0:
                    continue
                
                mean_lons = results[sat_name]['mean_lons']
                dates = results[sat_name]['dates']
                
                # Calculate deviation from designated if available
                designated_lon = None
                if sat_name in service_reqs:
                    req = service_reqs[sat_name]
                    if 'longitude' in req:
                        designated_lon = req['longitude']
                    elif 'central_longitude_deg' in req:
                        designated_lon = req['central_longitude_deg']
                
                current_lon = mean_lons[-1] if mean_lons else None
                deviation = None
                if designated_lon is not None and current_lon is not None:
                    diff = current_lon - designated_lon
                    while diff > 180:
                        diff -= 360
                    while diff < -180:
                        diff += 360
                    deviation = diff
                
                stats_data.append({
                    'Satellite': sat_name,
                    'Current Mean Lon (°)': f"{current_lon:.2f}" if current_lon else "N/A",
                    'Designated Lon (°)': f"{designated_lon:.2f}" if designated_lon else "N/A",
                    'Current Deviation (°)': f"{deviation:+.2f}" if deviation is not None else "N/A",
                    'Lon Range (°)': f"{min(mean_lons):.2f} to {max(mean_lons):.2f}",
                    'Data Points': len(mean_lons),
                    'Period': f"{min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')}"
                })
            
            if stats_data:
                stats_df = pd.DataFrame(stats_data)
                st.dataframe(stats_df, hide_index=True, use_container_width=True)
        
        st.caption("""
        **Notes:**
        - Each point represents the central (mean) longitude calculated from a historical TLE
        - Dashed lines show the designated longitude slot for each satellite
        - Central longitude is calculated using circular mean over a 24-hour window
        - For IGSO satellites, this represents the "waist" of their figure-8 ground track
        """)


def plot_mean_longitude_over_time(df_all, satellites, start_date, end_date, timestep_minutes=15):
    """
    Plot mean longitude variation over time for satellites.
    
    For each day:
    - Propagate satellite over ~24 hours
    - Compute sub-satellite longitude at fine resolution
    - Compute circular mean longitude
    - Slide the window forward in time
    - Plot longitude (X-axis) vs time (Y-axis)
    
    Args:
        df_all: DataFrame containing satellite data
        satellites: Dictionary of satellite objects from skyfield
        start_date: Start date for analysis
        end_date: End date for analysis
        timestep_minutes: Time resolution for propagation (default 15 minutes)
    """
    import numpy as np
    from skyfield.api import load, wgs84
    
    st.markdown("### 🌍 Mean Longitude Over Time (Last 30 Days)")
    st.caption("Central longitude stability analysis - shows mean longitude variation over the last month")
    
    with st.spinner("Calculating mean longitudes over time..."):
        ts = load.timescale()
        
        # Generate daily windows for the last 30 days
        # Calculate start date as 30 days before end_date
        last_month_start = end_date - timedelta(days=30)
        
        current_date = last_month_start
        date_range = []
        while current_date <= end_date:
            date_range.append(current_date)
            current_date += timedelta(days=1)
        
        # Store results for each satellite
        results = {sat_name: {'dates': [], 'mean_lons': [], 'lon_std': []} 
                   for sat_name in satellites.keys()}
        
        # Process each day
        for current_date in date_range:
            # Create 24-hour window starting from current date
            window_start = datetime.combine(current_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            
            # Generate time steps over 24 hours
            num_steps = int((24 * 60) / timestep_minutes)
            time_steps = []
            for i in range(num_steps):
                dt = window_start + timedelta(minutes=i * timestep_minutes)
                time_steps.append(dt)
            
            # For each satellite, compute longitude at each time step
            for sat_name, sat_obj in satellites.items():
                try:
                    longitudes = []
                    
                    for time_point in time_steps:
                        t = ts.from_datetime(time_point)
                        geocentric = sat_obj.at(t)
                        subpoint = wgs84.subpoint(geocentric)
                        longitudes.append(subpoint.longitude.degrees)
                    
                    # Compute circular mean longitude
                    # Convert to radians for circular statistics
                    lons_rad = np.deg2rad(longitudes)
                    
                    # Convert to unit vectors
                    x = np.cos(lons_rad)
                    y = np.sin(lons_rad)
                    
                    # Compute mean
                    mean_x = np.mean(x)
                    mean_y = np.mean(y)
                    
                    # Convert back to angle
                    mean_lon_rad = np.arctan2(mean_y, mean_x)
                    mean_lon = np.rad2deg(mean_lon_rad)
                    
                    # Compute circular standard deviation
                    R = np.sqrt(mean_x**2 + mean_y**2)
                    circular_std = np.rad2deg(np.sqrt(-2 * np.log(R)))
                    
                    # Store results
                    results[sat_name]['dates'].append(current_date)
                    results[sat_name]['mean_lons'].append(mean_lon)
                    results[sat_name]['lon_std'].append(circular_std)
                    
                except Exception as e:
                    # Skip this satellite for this date if there's an error
                    continue
        
        # Create plot with longitude on X-axis and time on Y-axis
        fig = go.Figure()
        
        for sat_name in sorted(satellites.keys()):
            if len(results[sat_name]['dates']) > 0:
                # Add trace with error bars showing longitude variation
                fig.add_trace(go.Scatter(
                    x=results[sat_name]['mean_lons'],
                    y=results[sat_name]['dates'],
                    mode='markers+lines',
                    name=sat_name,
                    error_x=dict(
                        type='data',
                        array=results[sat_name]['lon_std'],
                        visible=True
                    ),
                    marker=dict(size=6),
                    line=dict(width=2),
                    hovertemplate=(
                        f"<b>{sat_name}</b><br>" +
                        "Date: %{y|%Y-%m-%d}<br>" +
                        "Mean Longitude: %{x:.2f}°<br>" +
                        "Std Dev: %{error_x.array:.2f}°<br>" +
                        "<extra></extra>"
                    )
                ))
        
        # Update layout
        fig.update_layout(
            title="Mean Longitude vs Time (Longitude on X-axis)",
            xaxis_title="Mean Longitude (°)",
            yaxis_title="Date",
            hovermode='closest',
            height=600,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=12),
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.01
            ),
            margin=dict(t=60, b=40, l=60, r=150)
        )
        
        # Set X-axis range to standard longitude range
        fig.update_xaxes(
            range=[-180, 180],
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(128,128,128,0.2)',
            zeroline=True,
            zerolinewidth=2,
            zerolinecolor='rgba(128,128,128,0.5)'
        )
        
        fig.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(128,128,128,0.2)'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Add summary statistics
        with st.expander("📊 Mean Longitude Statistics", expanded=False):
            stats_data = []
            for sat_name in sorted(satellites.keys()):
                if len(results[sat_name]['mean_lons']) > 0:
                    mean_lons = results[sat_name]['mean_lons']
                    lon_stds = results[sat_name]['lon_std']
                    
                    stats_data.append({
                        'Satellite': sat_name,
                        'Avg Mean Lon (°)': f"{np.mean(mean_lons):.2f}",
                        'Lon Range (°)': f"{np.min(mean_lons):.2f} to {np.max(mean_lons):.2f}",
                        'Avg Std Dev (°)': f"{np.mean(lon_stds):.2f}",
                        'Days Analyzed': len(mean_lons)
                    })
            
            if stats_data:
                stats_df = pd.DataFrame(stats_data)
                st.dataframe(stats_df, hide_index=True, use_container_width=True)
            else:
                st.info("No statistics available")


def plot_mean_longitude_map(satellites, reference_time, timestep_minutes=15, system_label="NavIC"):
    """
    Plot current mean longitude positions on a world map with deviation analysis.
    
    Shows satellite positions at their mean longitude over the last 24 hours,
    with vertical lines indicating the longitude, markers, and deviation from designated slots.
    
    Args:
        satellites: Dictionary of satellite objects from skyfield
        reference_time: Current reference time (datetime)
        timestep_minutes: Time resolution for mean calculation (default 15 minutes)
        system_label: Name of the constellation (NavIC, QZSS, BeiDou-3)
    """
    import numpy as np
    from skyfield.api import load, wgs84
    from config.config import NAVIK_SERVICE_REQUIREMENTS, QZSS_SERVICE_REQUIREMENTS, BEIDOU3_SERVICE_REQUIREMENTS
    
    # Select appropriate service requirements based on system
    if system_label == "NavIC":
        service_reqs = NAVIK_SERVICE_REQUIREMENTS
    elif system_label == "QZSS":
        service_reqs = QZSS_SERVICE_REQUIREMENTS
    elif system_label == "BeiDou-3":
        service_reqs = BEIDOU3_SERVICE_REQUIREMENTS
    else:
        service_reqs = {}
    
    st.markdown("### 🗺️ Current Mean Longitude - Geographic View")
    st.caption("Shows satellite mean longitude positions over the last 24 hours on a world map")
    
    # Debug info - show satellite names being processed
    if service_reqs:
        with st.expander("🔍 Debug: Satellite Name Matching", expanded=False):
            st.caption(f"Satellite names in TLE data: {list(satellites.keys())}")
            st.caption(f"Satellite names in config: {list(service_reqs.keys())}")
    
    with st.spinner("Calculating current mean longitudes..."):
        ts = load.timescale()
        
        # Calculate mean longitude for each satellite over last 24 hours
        satellite_positions = []
        
        # Generate time steps over 24 hours before reference time
        num_steps = int((24 * 60) / timestep_minutes)
        time_steps = []
        for i in range(num_steps):
            dt = reference_time - timedelta(hours=24) + timedelta(minutes=i * timestep_minutes)
            time_steps.append(dt)
        
        colors = [
            'blue', 'red', 'green', 'purple', 'orange', 'darkred', 'lightblue',
            'darkgreen', 'cadetblue', 'darkpurple', 'pink', 'lightgreen'
        ]
        
        for idx, (sat_name, sat_obj) in enumerate(satellites.items()):
            try:
                longitudes = []
                latitudes = []
                
                for time_point in time_steps:
                    t = ts.from_datetime(time_point)
                    geocentric = sat_obj.at(t)
                    subpoint = wgs84.subpoint(geocentric)
                    longitudes.append(subpoint.longitude.degrees)
                    latitudes.append(subpoint.latitude.degrees)
                
                # Compute circular mean longitude
                lons_rad = np.deg2rad(longitudes)
                x = np.cos(lons_rad)
                y = np.sin(lons_rad)
                mean_x = np.mean(x)
                mean_y = np.mean(y)
                mean_lon_rad = np.arctan2(mean_y, mean_x)
                mean_lon = np.rad2deg(mean_lon_rad)
                
                # Compute mean latitude (regular mean is fine for latitude)
                mean_lat = np.mean(latitudes)
                
                # Compute circular standard deviation
                R = np.sqrt(mean_x**2 + mean_y**2)
                circular_std = np.rad2deg(np.sqrt(-2 * np.log(R))) if R > 0 else 0
                
                # Get designated longitude from config
                designated_lon = None
                matched_req = None
                
                # Try multiple matching strategies
                # 1. Exact match
                if sat_name in service_reqs:
                    matched_req = service_reqs[sat_name]
                else:
                    # 2. Case-insensitive match
                    for config_name, req in service_reqs.items():
                        if config_name.upper() == sat_name.upper():
                            matched_req = req
                            break
                    
                    # 3. Check if config name is contained in satellite name
                    if matched_req is None:
                        for config_name, req in service_reqs.items():
                            if config_name.upper() in sat_name.upper() or sat_name.upper() in config_name.upper():
                                matched_req = req
                                break
                
                if matched_req is not None:
                    if 'longitude' in matched_req:
                        designated_lon = matched_req['longitude']
                    elif 'central_longitude_deg' in matched_req:
                        designated_lon = matched_req['central_longitude_deg']
                
                # Compute deviation from designated longitude (handle wrap-around)
                deviation = None
                if designated_lon is not None:
                    # Compute shortest angular distance
                    diff = mean_lon - designated_lon
                    # Normalize to [-180, 180]
                    while diff > 180:
                        diff -= 360
                    while diff < -180:
                        diff += 360
                    deviation = diff
                
                satellite_positions.append({
                    'name': sat_name,
                    'mean_lon': mean_lon,
                    'mean_lat': mean_lat,
                    'lon_std': circular_std,
                    'designated_lon': designated_lon,
                    'deviation': deviation,
                    'color': colors[idx % len(colors)]
                })
                
            except Exception as e:
                continue
        
        if not satellite_positions:
            st.warning("No satellite position data available")
            return
        
        # Create Folium map centered on equator
        m = folium.Map(
            location=[0, 80],  # Centered on equator, near India region
            zoom_start=2,
            tiles='OpenStreetMap',
            control_scale=True
        )
        
        # Add different tile layers
        folium.TileLayer('CartoDB positron').add_to(m)
        folium.TileLayer('CartoDB dark_matter').add_to(m)
        
        # Add Google Maps layers
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
            attr='Google',
            name='Google Maps',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
            attr='Google',
            name='Google Satellite',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
            attr='Google',
            name='Google Hybrid',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
            attr='Google',
            name='Google Terrain',
            overlay=False,
            control=True
        ).add_to(m)
        
        # Add satellite markers and longitude lines
        for sat_pos in satellite_positions:
            sat_name = sat_pos['name']
            mean_lon = sat_pos['mean_lon']
            mean_lat = sat_pos['mean_lat']
            lon_std = sat_pos['lon_std']
            designated_lon = sat_pos['designated_lon']
            deviation = sat_pos['deviation']
            color = sat_pos['color']
            
            # Add vertical line at mean longitude (from -60° to +60° latitude)
            line_coords = []
            for lat in range(-60, 61, 5):
                line_coords.append([lat, mean_lon])
            
            folium.PolyLine(
                line_coords,
                color=color,
                weight=2,
                opacity=0.5,
                dash_array='5, 10',
                popup=f"{sat_name} - Mean Longitude Line",
                tooltip=f"{sat_name}: {mean_lon:.2f}°"
            ).add_to(m)
            
            # Add designated longitude line if available (lighter, dashed)
            if designated_lon is not None:
                des_line_coords = []
                for lat in range(-60, 61, 10):
                    des_line_coords.append([lat, designated_lon])
                
                folium.PolyLine(
                    des_line_coords,
                    color=color,
                    weight=1,
                    opacity=0.3,
                    dash_array='10, 10',
                    popup=f"{sat_name} - Designated Longitude",
                    tooltip=f"{sat_name} Designated: {designated_lon:.2f}°"
                ).add_to(m)
            
            # Add marker at mean latitude position
            popup_text = f"<b>{sat_name}</b><br>Mean Longitude: {mean_lon:.2f}°<br>Mean Latitude: {mean_lat:.2f}°<br>Std Dev: {lon_std:.2f}°"
            if designated_lon is not None:
                popup_text += f"<br>Designated: {designated_lon:.2f}°<br>Deviation: {deviation:+.2f}°"
            
            folium.CircleMarker(
                location=[mean_lat, mean_lon],
                radius=8,
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.9,
                popup=folium.Popup(popup_text, max_width=250),
                tooltip=f"{sat_name} ({mean_lon:.2f}°)"
            ).add_to(m)
            
            # Add label for satellite name
            folium.Marker(
                location=[mean_lat, mean_lon],
                icon=folium.DivIcon(html=f'''
                    <div style="font-size: 10pt; color: {color}; font-weight: bold; 
                                white-space: nowrap; text-shadow: 1px 1px 2px white;">
                        {sat_name}
                    </div>
                ''')
            ).add_to(m)
        
        # Add equator line
        folium.PolyLine(
            [[0, lon] for lon in range(-180, 181, 10)],
            color='gray',
            weight=1,
            opacity=0.3,
            dash_array='2, 5',
            popup="Equator",
            tooltip="Equator (0°)"
        ).add_to(m)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Add title
        title_html = f'''
        <div style="position: fixed; 
                    top: 10px; 
                    left: 50px; 
                    width: 450px; 
                    height: 60px; 
                    background-color: white; 
                    border:2px solid grey; 
                    z-index:9999; 
                    font-size:14px;
                    padding: 10px;
                    border-radius: 5px;
                    box-shadow: 2px 2px 6px rgba(0,0,0,0.3);">
        <b>{system_label} Satellite Mean Longitude Positions</b><br>
        <small>Based on 24-hour window ending {reference_time.strftime('%Y-%m-%d %H:%M UTC')}</small>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(title_html))
        
        # Display the map in Streamlit
        st_folium(m, width=None, height=600, returned_objects=[])
        
        # Add deviation table
        st.markdown("#### 📊 Longitude Slot Deviation Analysis")
        deviation_data = []
        for sat_pos in sorted(satellite_positions, key=lambda x: x['name']):
            row = {
                'Satellite': sat_pos['name'],
                'Current Mean Lon (°)': f"{sat_pos['mean_lon']:.2f}",
                'Designated Lon (°)': f"{sat_pos['designated_lon']:.2f}" if sat_pos['designated_lon'] is not None else "N/A",
                'Deviation (°)': f"{sat_pos['deviation']:+.2f}" if sat_pos['deviation'] is not None else "N/A",
                'Longitude Std Dev (°)': f"{sat_pos['lon_std']:.2f}"
            }
            deviation_data.append(row)
        
        deviation_df = pd.DataFrame(deviation_data)
        
        # Style the dataframe to highlight deviations
        def highlight_deviation(row):
            if row['Deviation (°)'] == "N/A":
                return [''] * len(row)
            
            try:
                dev_val = float(row['Deviation (°)'])
                abs_dev = abs(dev_val)
                
                # Color based on deviation magnitude
                if abs_dev > 1.0:
                    color = 'background-color: #ffcccc'  # Light red
                elif abs_dev > 0.5:
                    color = 'background-color: #ffffcc'  # Light yellow
                else:
                    color = 'background-color: #ccffcc'  # Light green
                
                return ['', '', '', color, '']
            except:
                return [''] * len(row)
        
        st.dataframe(
            deviation_df.style.apply(highlight_deviation, axis=1),
            hide_index=True,
            use_container_width=True
        )
        
        # Add explanation
        st.caption("""
        **Legend:** 
        - 🟢 Green: Deviation ≤ 0.5° (Good) 
        - 🟡 Yellow: Deviation 0.5° - 1.0° (Acceptable)
        - 🔴 Red: Deviation > 1.0° (Needs Attention)
        
        *Solid lines show current mean longitude. Light dashed lines show designated longitude slots.*
        """)

