# Socket Version Fix - Revert Instructions

## What Was Changed
**Date**: 2026-02-23
**File**: JunkOS-Driver/Services/SocketIOManager.swift
**Lines**: 47-51

## Change Made
Removed Socket.IO v2 protocol enforcement to allow app to use v4 protocol (matching backend).

### BEFORE (lines 47-51):
```swift
.extraHeaders(["X-Client-Type": "ios-driver"]),  // Help backend identify mobile clients
// CRITICAL: Force Socket.IO v2 (Engine.IO v3) to avoid batched POST issues
// Engine.IO v4 batches messages with ^^ delimiter, which Render's proxy rejects
// Causing "Error flushing waiting posts" and connection drops
.version(.two)  // Single POST per packet - works reliably with Render
```

### AFTER (lines 47-49):
```swift
.extraHeaders(["X-Client-Type": "ios-driver"])  // Help backend identify mobile clients
// Removed .version(.two) to match backend Engine.IO v4 protocol
// Backend requires v4 (python-socketio >= 5.11.0)
```

## Why This Was Changed
- Backend only supports Engine.IO v4 (python-socketio >= 5.11.0)
- iOS app was forcing v2/v3 protocol
- Backend rejected v3 connections with "unsupported version" error
- No socket connections could be established

## How to Revert If Needed

If socket connections fail or "Error flushing waiting posts" errors return:

```bash
cd /Users/sevs/vivi/junkos/JunkOS-Driver/Services
git checkout HEAD~1 -- SocketIOManager.swift
```

Or manually edit line 47-49 to restore:
```swift
.extraHeaders(["X-Client-Type": "ios-driver"]),  // Help backend identify mobile clients
// CRITICAL: Force Socket.IO v2 (Engine.IO v3) to avoid batched POST issues
// Engine.IO v4 batches messages with ^^ delimiter, which Render's proxy rejects
// Causing "Error flushing waiting posts" and connection drops
.version(.two)  // Single POST per packet - works reliably with Render
```

## Testing After Fix
1. Rebuild app: `xcodebuild clean build ...`
2. Launch in simulator
3. Authenticate as driver
4. Toggle online
5. Check logs for:
   - ✅ "SocketIO: Connected!"
   - ✅ "SocketIO: Joined driver room: driver:xxx"
   - ❌ NO "unsupported version" errors
   - ❌ NO "Error flushing waiting posts" errors

## Backend Info
- URL: https://junkos-backend.onrender.com
- Socket.IO: v3+ (Engine.IO v4)
- Health: https://junkos-backend.onrender.com/api/health
- Version shows: "socketio-v4-protocol"
