// Optional: Set your Cesium Ion token if using terrain
Cesium.Ion.defaultAccessToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiI3NjcyMmE3NC1iNzU3LTQyODMtOTJhMy1hZmMzNDc2NjgzNjciLCJpZCI6MzA0NTUyLCJpYXQiOjE3NDc3Njc5ODF9.phwkbWNFGfzSktJrMnqtl75IDCixo0kDYgvZaIGdi4I';

const viewer = new Cesium.Viewer('cesiumContainer', {
    shouldAnimate: true,
    baseLayerPicker: true,
    timeline: true,
    animation: true
});

let otherSatellitesDataSource = null;

// Load your satellite CZML file
Cesium.CzmlDataSource.load('your_satellite.czml')
    .then(function(dataSource) {
        viewer.dataSources.add(dataSource);
        console.log("✅ Main satellite CZML loaded.");
        viewer.flyTo(dataSource.entities);
    })
    .catch(function(error) {
        console.error("❌ Error loading main satellite CZML:", error);
    });

// Load other satellites as dynamic CZML
Cesium.CzmlDataSource.load('other_satellites.czml')
    .then(function(dataSource) {
        viewer.dataSources.add(dataSource);
        otherSatellitesDataSource = dataSource;
        console.log("✅ Other satellites CZML loaded.");
        const entities = dataSource.entities.values;
        console.log(`✅ Loaded ${entities.length} other satellites.`);
    })
    .catch(function(error) {
        console.error("❌ Error loading other satellites CZML:", error);
    });

// Load close approaches JSON and populate dropdown with sorting/filtering
fetch('close_approaches.json')
    .then(response => response.json())
    .then(data => {
        console.log("✅ Close approaches JSON loaded.");

        const dropdown = document.getElementById('approachDropdown');
        const sortDropdown = document.getElementById('sortDropdown');
        const filterInput = document.getElementById('filterInput');
        const toggleLabelsCheckbox = document.getElementById('toggleLabels');

        const originalData = data.slice();  // store original data

        function populateDropdown(items) {
            dropdown.innerHTML = '<option value="">Select a Close Approach</option>';
            items.forEach(approach => {
                const option = document.createElement('option');
                option.value = approach.datetime;
                option.text = `${approach.datetime} | ${approach.sat_name} (${approach.distance_km} km)`;
                dropdown.appendChild(option);
            });
        }

        function sortAndFilter() {
            let workingData = originalData.slice();  // Always start fresh

            const sortBy = sortDropdown.value;
            if (sortBy === 'datetime') {
                workingData.sort((a, b) => new Date(a.datetime) - new Date(b.datetime));
            } else if (sortBy === 'distance') {
                workingData.sort((a, b) => a.distance_km - b.distance_km);
            } else if (sortBy === 'name') {
                workingData.sort((a, b) => a.sat_name.localeCompare(b.sat_name));
            }

            const filterText = filterInput.value.toLowerCase();
            if (filterText) {
                workingData = workingData.filter(approach =>
                    approach.sat_name.toLowerCase().includes(filterText)
                );
            }

            populateDropdown(workingData);
        }

        // Initial population
        sortAndFilter();

        // Event listeners
        sortDropdown.addEventListener('change', sortAndFilter);
        filterInput.addEventListener('input', sortAndFilter);

dropdown.addEventListener('change', function() {
    const selectedTime = this.value;
    if (selectedTime) {
        const cesiumTime = Cesium.JulianDate.fromDate(new Date(selectedTime));
        viewer.clock.currentTime = cesiumTime;
        viewer.clock.shouldAnimate = false;
        console.log(`⏰ Jumped to time: ${selectedTime}`);

        const selectedApproach = originalData.find(approach => approach.datetime === selectedTime);
        if (selectedApproach) {
            const infoHtml = `
                <strong>Satellite:</strong> ${selectedApproach.sat_name}<br>
                <strong>Country:</strong> ${selectedApproach.country || 'UNKNOWN'}<br>
                <strong>Distance:</strong> ${selectedApproach.distance_km} km<br>
                <strong>Total Relative Velocity:</strong> ${parseFloat(selectedApproach.relative_velocity_kms).toFixed(3)} km/s<br>
                <strong>Radial Velocity:</strong> ${selectedApproach.rel_vel_radial_kms !== null ? parseFloat(selectedApproach.rel_vel_radial_kms).toFixed(3) : 'N/A'} km/s<br>
                <strong>Tangential Velocity:</strong> ${selectedApproach.rel_vel_tangential_kms !== null ? parseFloat(selectedApproach.rel_vel_tangential_kms).toFixed(3) : 'N/A'} km/s<br>
                <strong>Angular Velocity:</strong> ${selectedApproach.angular_velocity_deg_per_sec !== null ? parseFloat(selectedApproach.angular_velocity_deg_per_sec).toFixed(6) : 'N/A'} deg/s<br>
                <strong>Azimuth:</strong> ${selectedApproach.azimuth_deg !== null ? parseFloat(selectedApproach.azimuth_deg).toFixed(2) : 'N/A'} deg<br>
                <strong>Elevation:</strong> ${selectedApproach.elevation_deg !== null ? parseFloat(selectedApproach.elevation_deg).toFixed(2) : 'N/A'} deg<br>
                <strong>Sunlit:</strong> ${selectedApproach.sunlit ? 'Yes' : 'No'}<br>
                <strong>You between Sun and Target:</strong> ${selectedApproach.you_between_sun_and_target ? 'Yes' : 'No'}
            `;
            document.getElementById('infoContent').innerHTML = infoHtml;


            const entityId = `sat_${selectedApproach.norad_id}`;
            const targetEntity = otherSatellitesDataSource && otherSatellitesDataSource.entities.getById(entityId);

            if (targetEntity) {
                // Reset all satellite points to default
                otherSatellitesDataSource.entities.values.forEach(entity => {
                    if (entity.point) {
                        entity.point.pixelSize = 4;
                        entity.point.color = Cesium.Color.WHITE;
                    }
                });

                // Highlight the selected satellite
                if (targetEntity.point) {
                    targetEntity.point.pixelSize = 10;
                    targetEntity.point.color = Cesium.Color.YELLOW;
                }

                // Fly the camera to the satellite
                viewer.flyTo(targetEntity, {
                    duration: 2.0,
                    offset: new Cesium.HeadingPitchRange(
                        0.0,
                        -Cesium.Math.PI_OVER_FOUR,
                        1000000
                    )
                });
                console.log(`🎯 Camera flying to ${selectedApproach.sat_name}`);
            } else {
                console.warn(`⚠️ Target satellite entity not found: ${entityId}`);
            }
        } else {
            document.getElementById('infoContent').innerHTML = "No data available.";
        }
    } else {
        document.getElementById('infoContent').innerHTML = "Select a close approach to see details here.";
    }
});




        // Label toggle handler
toggleLabelsCheckbox.addEventListener('change', function() {
    if (!otherSatellitesDataSource) {
        console.warn("⚠️ Other satellites data not loaded yet.");
        return;
    }

    const showLabels = toggleLabelsCheckbox.checked;
    otherSatellitesDataSource.entities.values.forEach(entity => {
        let name = "Unknown";
        if (entity.name) {
            name = entity.name;
        } else if (entity.id) {
            name = entity.id;
        }
        console.log(`🔎 Checking entity: ID=${entity.id}, name=${name}`);

        if (!entity.label) {
            entity.label = new Cesium.LabelGraphics({
                text: name,
                font: '10px sans-serif',
                showBackground: true,
                backgroundColor: Cesium.Color.BLACK.withAlpha(0.5),
                horizontalOrigin: Cesium.HorizontalOrigin.LEFT,
                pixelOffset: new Cesium.Cartesian2(10, 0),
                fillColor: Cesium.Color.WHITE,
                show: showLabels
            });
            console.log(`🛰️ Label created for: ${name}`);
        } else {
            entity.label.show = showLabels;
            console.log(`🛰️ Label toggled for: ${name}`);
        }
    });
    console.log(`📝 Labels toggled: ${showLabels ? 'ON' : 'OFF'}`);
});


    })
    .catch(error => console.error("❌ Error loading close approaches JSON:", error));
