# Velocity Proxy Guide for auto-mcs

## Overview

Velocity is a modern, high-performance Minecraft proxy designed to connect multiple Minecraft servers together in a network. auto-mcs now supports Velocity proxy alongside the existing playit.gg integration.

## What is Velocity?

Velocity is a next-generation Minecraft proxy that allows players to seamlessly switch between multiple Minecraft servers while maintaining a single connection. It's the successor to BungeeCord and Waterfall, offering:

- **Better Performance**: Built from the ground up for speed and efficiency
- **Modern Forwarding**: Secure player information forwarding with cryptographic verification
- **Backwards Compatibility**: Supports legacy BungeeCord forwarding mode
- **Plugin Support**: Compatible with Velocity plugins
- **Active Development**: Maintained by the PaperMC team

## Features in auto-mcs

The Velocity integration in auto-mcs provides:

1. **Automatic Installation**: Download and install Velocity with one click
2. **Configuration Management**: Automatically generate velocity.toml configuration
3. **Modern/Legacy Forwarding**: Support for both Velocity native and BungeeCord modes
4. **Backend Server Management**: Add/remove servers to your Velocity network
5. **Secret Key Generation**: Automatic secure forwarding secret generation
6. **Port Configuration**: Customize your Velocity proxy port

## Getting Started

### Installing Velocity

Using the auto-mcs API:

```python
from source.core.server import velocity

# Initialize the Velocity manager
velocity.init_manager()

# Install the latest version
velocity.manager.install_velocity()

# Or install a specific version
velocity.manager.install_velocity(version="3.3.0")
```

### Basic Configuration

```python
# Configure Velocity with default settings
velocity.manager.configure_velocity(
    port=25577,
    forwarding_mode='modern'
)

# Start the Velocity proxy
velocity.manager.start_velocity()
```

### Adding Backend Servers

```python
# Add a backend server to the network
velocity.manager.add_server_connection(
    name="lobby",
    address="127.0.0.1",
    port=25565
)

velocity.manager.add_server_connection(
    name="survival",
    address="127.0.0.1",
    port=25566
)

# Regenerate configuration with new servers
velocity.manager.configure_velocity()
```

## Forwarding Modes

### Modern Forwarding (Recommended)

Modern forwarding uses cryptographic verification to ensure player information is authentic:

```python
velocity.manager.configure_velocity(forwarding_mode='modern')
```

**Backend Server Setup:**
- For Paper 1.19+, the backend server's `config/paper-global.yml` will be automatically configured
- The forwarding secret is shared between Velocity and backend servers
- Set `online-mode=false` in backend server's `server.properties`

### Legacy Forwarding (BungeeCord)

For compatibility with older setups:

```python
velocity.manager.configure_velocity(forwarding_mode='legacy')
```

**Backend Server Setup:**
- For Spigot/Paper, set `bungeecord: true` in `spigot.yml`
- Set `online-mode=false` in `server.properties`

## Using Velocity with ServerObject

### Enable Velocity for a Server

```python
from source.core.server.manager import ServerManager

# Get your server
server_manager = ServerManager()
server = server_manager.get_server("my-server")

# Enable Velocity
server.enable_velocity(True)

# Configure Velocity settings
server.set_velocity_config(
    port=25577,
    mode='modern'
)
```

### Add Server to Network

```python
# Add this server as a backend to Velocity
server.add_to_velocity_network(proxy_server=None)

# This will:
# 1. Add the server to Velocity's configuration
# 2. Configure forwarding on the backend server
# 3. Update the server's auto-mcs.ini
```

### Check Installation Status

```python
# Check if Velocity is installed
if server.velocity_installed():
    print("Velocity is ready!")
else:
    # Install it
    server.install_velocity()
```

### Get Configuration

```python
# Get current Velocity configuration
config = server.get_velocity_config()
print(f"Enabled: {config['enabled']}")
print(f"Port: {config['port']}")
print(f"Mode: {config['mode']}")
print(f"Running: {config['manager_config']['running']}")
```

## Configuration File Structure

### velocity.toml

The Velocity configuration file is generated automatically:

```toml
config-version = "2.7"

# Bind address
bind = "0.0.0.0:25577"

# MOTD
motd = "&#09add3A Velocity Server"

# Online mode
online-mode = true

# Player info forwarding
player-info-forwarding-mode = "modern"
forwarding-secret = "your-secret-key-here"

# Server list
[servers]
lobby = "127.0.0.1:25565"
survival = "127.0.0.1:25566"

# Try order
try = ["lobby", "survival"]

[advanced]
compression-threshold = 256
compression-level = -1
login-ratelimit = 3000
connection-timeout = 5000
read-timeout = 30000
```

### auto-mcs.ini (Server Config)

Velocity settings are stored in each server's `auto-mcs.ini`:

```ini
[general]
enableVelocity = true
velocityPort = 25577
velocityMode = modern
```

## Network Architecture

### Example Multi-Server Setup

```
Player → Velocity Proxy (port 25577)
         ├─→ Lobby Server (port 25565)
         ├─→ Survival Server (port 25566)
         ├─→ Creative Server (port 25567)
         └─→ Minigames Server (port 25568)
```

### Port Configuration

- **Velocity Proxy**: Default port 25577 (customizable)
- **Backend Servers**: Each server needs its own unique port
- Players connect to the Velocity proxy port only

## Security Considerations

### Forwarding Secret

The forwarding secret is a cryptographic key that:
- Verifies player information from Velocity to backend servers
- Prevents unauthorized servers from connecting
- Is automatically generated and stored in `forwarding.secret`
- Must match between Velocity and all backend servers

**Never share your forwarding secret publicly!**

### Firewall Configuration

Only expose the Velocity proxy port to the internet:
- ✅ Expose: Velocity port (25577)
- ❌ Do not expose: Backend server ports (25565, 25566, etc.)

## Troubleshooting

### Players Can't Connect

1. Check if Velocity is running:
   ```python
   config = velocity.manager.get_velocity_config()
   print(config['running'])
   ```

2. Verify port is not in use:
   ```bash
   netstat -ano | findstr :25577
   ```

3. Check firewall rules allow the Velocity port

### Backend Servers Not Reachable

1. Ensure backend servers are running
2. Verify ports in Velocity configuration match backend server ports
3. Check `server.properties` has `online-mode=false`
4. Verify forwarding is configured correctly

### Forwarding Issues

1. **Modern mode**: Ensure `forwarding.secret` matches in:
   - Velocity: `velocity.toml`
   - Backend: `config/paper-global.yml`

2. **Legacy mode**: Ensure `bungeecord: true` in `spigot.yml`

### Connection Refused

1. Check backend server is running:
   ```python
   server.running
   ```

2. Verify IP address (use 127.0.0.1 for local servers)
3. Check server logs for errors

## API Reference

### VelocityManager Methods

#### Installation
- `install_velocity(version=None, progress_func=None)` - Install Velocity
- `uninstall_velocity(keep_config=True)` - Uninstall Velocity
- `update_velocity()` - Update to latest version

#### Configuration
- `configure_velocity(port=25577, forwarding_mode='modern')` - Generate config
- `add_server_connection(name, address, port)` - Add backend server
- `remove_server_connection(name)` - Remove backend server
- `enable_forwarding(server_path)` - Configure backend for forwarding

#### Runtime
- `start_velocity()` - Start proxy
- `stop_velocity()` - Stop proxy
- `get_velocity_config()` - Get current configuration

### ServerObject Methods

#### Management
- `velocity_installed()` - Check if installed
- `install_velocity(version=None)` - Install Velocity
- `enable_velocity(enabled)` - Enable/disable for server

#### Configuration
- `get_velocity_config()` - Get configuration
- `set_velocity_config(port, mode)` - Update settings
- `add_to_velocity_network(proxy_server)` - Add to network

## Best Practices

### 1. Use Modern Forwarding
Modern forwarding provides better security and is recommended for all new setups.

### 2. Separate Lobby Server
Create a dedicated lobby server that players spawn into first.

### 3. Resource Allocation
- Velocity proxy: 512MB-1GB RAM (lightweight)
- Backend servers: Allocate based on player count and plugins

### 4. Backup Configuration
Always backup your `velocity.toml` and `forwarding.secret` files.

### 5. Regular Updates
Keep Velocity updated for security patches and performance improvements:
```python
velocity.manager.update_velocity()
```

## Example: Complete Network Setup

```python
from source.core.server import velocity
from source.core.server.manager import ServerManager

# Initialize
velocity.init_manager()
manager = ServerManager()

# Install Velocity
velocity.manager.install_velocity()

# Configure Velocity
velocity.manager.configure_velocity(port=25577, forwarding_mode='modern')

# Add backend servers
velocity.manager.add_server_connection("lobby", "127.0.0.1", 25565)
velocity.manager.add_server_connection("survival", "127.0.0.1", 25566)
velocity.manager.add_server_connection("creative", "127.0.0.1", 25567)

# Regenerate configuration
velocity.manager.configure_velocity(port=25577, forwarding_mode='modern')

# Configure each backend server
for server_name in ["lobby", "survival", "creative"]:
    server = manager.get_server(server_name)
    server.enable_velocity(True)
    velocity.manager.enable_forwarding(server.server_path)

# Start Velocity
velocity.manager.start_velocity()

print("✅ Velocity network is ready!")
print(f"Connect to: localhost:25577")
```

## Comparison: Velocity vs. playit.gg

| Feature | Velocity | playit.gg |
|---------|----------|-----------|
| **Purpose** | Multi-server network | Port forwarding/tunneling |
| **Use Case** | Connect multiple servers | Expose local server to internet |
| **Performance** | Native, very fast | Slight overhead from tunnel |
| **Setup** | More complex | Very simple |
| **Cost** | Free, self-hosted | Free with limitations |
| **Security** | Full control | Depends on service |
| **Flexibility** | High | Medium |

**Can you use both?**
Yes! You can run Velocity locally to connect multiple servers, then use playit.gg to expose the Velocity proxy port to the internet.

## Further Resources

- [Velocity Documentation](https://velocitypowered.com/wiki/)
- [PaperMC Downloads](https://papermc.io/downloads/velocity)
- [Velocity Discord](https://discord.gg/papermc)

## Support

For issues with the Velocity integration in auto-mcs:
1. Check the troubleshooting section above
2. Review auto-mcs logs for error messages
3. Open an issue on the auto-mcs GitHub repository

For general Velocity questions:
- Visit the [Velocity Wiki](https://velocitypowered.com/wiki/)
- Join the [PaperMC Discord](https://discord.gg/papermc)
