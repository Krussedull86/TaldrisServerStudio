//
// Initialize bootstrap toasts
//
window.toastElList = document.querySelectorAll('.toast');
window.toastList = [...toastElList].map(toastEl => new bootstrap.Toast(toastEl));

//
// Initialize bootstrap tooltips
//
const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl))

//
// Toast message: Save progress
//
window.toastSaveElement = document.getElementById('toastSave');
window.toastSaveBootstrap = bootstrap.Toast.getOrCreateInstance(toastSaveElement);

// Function to change the toast message and show the toast
window.showToastSave = function(message) {
	// Set the new message
	window.toastSaveElement.querySelector('.toast-body').textContent = message;
	// Show the toast
	window.toastSaveBootstrap.show();
}

//
// Toast message: Tools feedback
//
window.toastToolsElement = document.getElementById('toastTools');
window.toastToolsBootstrap = bootstrap.Toast.getOrCreateInstance(toastToolsElement);

// Function to change the toast message and show the toast
window.showToastTools = function(message) {
	// Set the new message
	window.toastToolsElement.querySelector('.toast-body').textContent = message;
	// Show the toast
	window.toastToolsBootstrap.show();
}

//
// Toast message: Error feedback
//
window.toastErrorElement = document.getElementById('toastError');
window.toastErrorBootstrap = bootstrap.Toast.getOrCreateInstance(toastErrorElement);

// Function to change the toast message and show the toast
window.showToastError = function(message) {
	// Set the new message
	window.toastErrorElement.querySelector('.toast-body').textContent = message;
	// Show the toast
	window.toastErrorBootstrap.show();
}

//
// Initialize JS files depending on current page
//
document.addEventListener('DOMContentLoaded', () => { window.startDesktop().catch(e => window.showToastError(e.message)); });
