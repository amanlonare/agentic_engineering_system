// web_app/api.js

/**
 * Calls the UserService.create_user endpoint.
 * Note: This depends on the service_api backend.
 */
async function registerUser(username, email) {
    const response = await fetch('/api/users', {
        method: 'POST',
        body: JSON.stringify({ username, email })
    });
    return response.json();
}
