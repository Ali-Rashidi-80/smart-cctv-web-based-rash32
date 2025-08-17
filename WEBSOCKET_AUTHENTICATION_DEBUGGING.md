# WebSocket Authentication Debugging Improvements

## Issue Identified

After implementing the WebSocket authentication fixes, a new issue emerged: the client-side authentication check was failing even though the server recognized the user as authenticated. This caused the system to prevent WebSocket connections with the message "User not authenticated, cannot establish WebSocket connection".

## Root Cause Analysis

The problem was in the client-side authentication validation:

1. **Token Retrieval Issues**: The `getAuthToken()` method might not be finding the authentication token in the expected locations
2. **JWT Parsing Errors**: The `isAuthenticated()` method was failing to parse JWT tokens correctly
3. **No Fallback Mechanism**: When token validation failed, there was no alternative authentication method
4. **Async Handling**: The authentication check was synchronous but needed to handle async operations

## Solutions Implemented

### 1. Enhanced Token Retrieval (`getAuthToken`)

Added comprehensive debugging and multiple fallback sources:

```javascript
getAuthToken() {
    // Try localStorage first
    let token = localStorage.getItem('access_token');
    console.log('[DEBUG] Token from localStorage:', token ? 'Found' : 'Not found');
    
    // Try cookies with multiple naming patterns
    if (!token) {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'access_token' || name === 'token') {
                token = value;
                console.log('[DEBUG] Token found in cookie:', name);
                break;
            }
        }
    }
    
    // Try sessionStorage
    if (!token) {
        token = sessionStorage.getItem('access_token');
        console.log('[DEBUG] Token from sessionStorage:', token ? 'Found' : 'Not found');
    }
    
    // Search for any cookie containing 'token' or 'auth'
    if (!token) {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            if (cookie.includes('token') || cookie.includes('auth')) {
                console.log('[DEBUG] Found potential auth cookie:', cookie);
                const [name, value] = cookie.trim().split('=');
                if (value && value.length > 10) {
                    token = value;
                    console.log('[DEBUG] Using token from cookie:', name);
                    break;
                }
            }
        }
    }
    
    console.log('[DEBUG] Final token result:', token ? 'Token found' : 'No token found');
    return token;
}
```

### 2. Improved Authentication Validation (`isAuthenticated`)

Enhanced JWT parsing and added fallback mechanisms:

```javascript
async isAuthenticated() {
    const token = this.getAuthToken();
    if (!token) {
        console.log('[DEBUG] No token found for authentication check');
        // Fallback to server check
        return await this.checkServerAuth();
    }
    
    console.log('[DEBUG] Checking authentication for token length:', token.length);
    
    try {
        // Handle different token formats
        let payload;
        if (token.includes('.')) {
            // JWT token format
            const parts = token.split('.');
            if (parts.length !== 3) {
                console.warn('[DEBUG] Invalid JWT token format, parts:', parts.length);
                return await this.checkServerAuth();
            }
            payload = JSON.parse(atob(parts[1]));
        } else {
            // Simple token format
            console.log('[DEBUG] Non-JWT token format detected, treating as valid');
            return true;
        }
        
        const now = Math.floor(Date.now() / 1000);
        const isExpired = payload.exp && payload.exp < now;
        
        console.log('[DEBUG] Token expiration check:', {
            tokenExp: payload.exp,
            currentTime: now,
            isExpired: isExpired
        });
        
        if (isExpired) {
            console.log('[DEBUG] Token expired, trying server auth check');
            return await this.checkServerAuth();
        }
        
        return true;
    } catch (e) {
        console.warn('[DEBUG] Error parsing token:', e);
        console.log('[DEBUG] Token that caused error:', token.substring(0, 50) + '...');
        // Fallback to server check
        return await this.checkServerAuth();
    }
}
```

### 3. Server-Side Authentication Fallback (`checkServerAuth`)

Added a method to verify authentication with the server:

```javascript
async checkServerAuth() {
    try {
        // Try to get user settings as a simple auth check
        const response = await fetch('/get_user_settings', {
            method: 'GET',
            credentials: 'include'
        });
        
        if (response.ok) {
            console.log('[DEBUG] Server authentication check successful');
            return true;
        } else if (response.status === 401) {
            console.log('[DEBUG] Server authentication check failed: Unauthorized');
            return false;
        } else {
            console.log('[DEBUG] Server authentication check status:', response.status);
            return false;
        }
    } catch (error) {
        console.error('[DEBUG] Server authentication check error:', error);
        return false;
    }
}
```

### 4. Async Method Updates

Updated all methods that call `setupWebSocket` to handle async operations:

```javascript
// In toggleStream method
await this.setupWebSocket();

// In reconnection logic
this.setupWebSocket().catch(err => console.error('[DEBUG] Reconnection error:', err));

// In timeout callbacks
setTimeout(async () => await this.setupWebSocket(), 1000);
```

## Debugging Features Added

### 1. Comprehensive Logging
- Token retrieval from each source
- Token format validation
- JWT parsing details
- Expiration time comparisons
- Server authentication check results

### 2. Error Handling
- Graceful fallbacks when token parsing fails
- Server-side authentication as backup
- Detailed error messages for troubleshooting

### 3. Token Format Support
- JWT tokens (3-part format)
- Simple tokens (non-JWT)
- Multiple cookie naming patterns
- localStorage and sessionStorage support

## Benefits

1. **Better Debugging**: Comprehensive logging helps identify authentication issues
2. **Robust Fallbacks**: Multiple authentication methods ensure connection success
3. **Flexible Token Handling**: Supports various token formats and storage locations
4. **Server Verification**: Fallback to server-side authentication when client-side fails
5. **Improved User Experience**: Clear error messages and automatic recovery

## Testing Recommendations

1. **Check Console Logs**: Monitor the detailed authentication debugging output
2. **Verify Token Storage**: Check where authentication tokens are stored
3. **Test Token Formats**: Ensure JWT tokens are properly formatted
4. **Monitor Server Auth**: Verify server-side authentication fallback works
5. **Test Reconnection**: Ensure WebSocket reconnection handles async authentication

## Expected Console Output

When working correctly, you should see:

```
[DEBUG] Token from localStorage: Found
[DEBUG] Final token result: Token found
[DEBUG] Checking authentication for token length: 123
[DEBUG] Token expiration check: {tokenExp: 1755198637, currentTime: 1755195037, isExpired: false}
[DEBUG] User authentication check successful
[DEBUG] Attempting WebSocket connection to: wss://host/ws/video
```

## Conclusion

These debugging improvements provide comprehensive visibility into the authentication process and ensure robust WebSocket connections even when client-side token validation fails. The system now has multiple fallback mechanisms and detailed logging to help identify and resolve authentication issues. 