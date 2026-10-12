function deleteSchedule(scheduleId) {
    if (confirm('Are you sure you want to delete this schedule?')) {
        showLoading();
        // Delete from Firestore (implement server-side endpoint if needed)
        fetch(`/delete_schedule/${scheduleId}`, { method: 'DELETE' })
            .then(() => {
                hideLoading();
                window.location.reload();
            })
            .catch(() => {
                hideLoading();
                alert('Failed to delete schedule.');
            });
    }
}