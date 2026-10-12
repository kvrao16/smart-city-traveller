function initMap() {
    const map = new google.maps.Map(document.getElementById('map'), {
        zoom: 12,
        center: { lat: 40.7128, lng: -74.0060 } // Default: New York
    });
    const directionsService = new google.maps.DirectionsService();
    const directionsRenderer = new google.maps.DirectionsRenderer();
    directionsRenderer.setMap(map);

    // Fetch venues from server (stored in session)
    fetch('/results').then(response => response.json()).then(data => {
        const venues = data.venues || [];
        const markers = venues.map(item => {
            const marker = new google.maps.Marker({
                position: { lat: item.venue.location.lat, lng: item.venue.location.lng },
                map: map,
                title: item.venue.name
            });
            marker.addListener('click', () => {
                new google.maps.InfoWindow({
                    content: `<h3>${item.venue.name}</h3><p>${item.venue.location.address}</p><p>Rating: ${item.venue.rating || 'N/A'}</p>`
                }).open(map, marker);
            });
            return marker;
        });

        // Calculate and display shortest route
        if (venues.length > 1) {
            const waypoints = venues.slice(1, -1).map(item => ({
                location: { lat: item.venue.location.lat, lng: item.venue.location.lng },
                stopover: true
            }));
            directionsService.route({
                origin: { lat: venues[0].venue.location.lat, lng: venues[0].venue.location.lng },
                destination: { lat: venues[venues.length - 1].venue.location.lat, lng: venues[venues.length - 1].venue.location.lng },
                waypoints: waypoints,
                travelMode: 'DRIVING'
            }, (response, status) => {
                if (status === 'OK') {
                    directionsRenderer.setDirections(response);
                } else {
                    alert('Failed to calculate route: ' + status);
                }
            });
        }
    });
}