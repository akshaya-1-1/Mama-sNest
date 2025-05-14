document.getElementById("forgotPasswordBtn").addEventListener("click", function(event) {
    event.preventDefault(); // Prevent default form submission

    const emailInput = document.getElementById("email");
    const messageBox = document.getElementById("message");
    const email = emailInput.value.trim();

    messageBox.innerText = ""; // Clear previous message

    // Basic validation
    if (!email) {
        messageBox.innerText = "Please enter your email address.";
        return;
    }

    // Optional: Show loading message
    messageBox.innerText = "Sending reset link...";

    // Send AJAX POST request to the server
    fetch("/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: `email=${encodeURIComponent(email)}`
    })
    .then(response => response.text())
    .then(data => {
        console.log("Response from server:", data);
        messageBox.innerText = data; // Display server response
    })
    .catch(error => {
        console.error("Error:", error);
        messageBox.innerText = "An error occurred. Please try again later.";
    });
});
