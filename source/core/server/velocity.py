from datetime import datetime as dt
from typing import Optional
import subprocess
import requests
import typing
import psutil
import secrets
import base64
import time
import json
import os
import re

try:
    import toml
except ImportError:
    toml = None

try:
    import yaml
except ImportError:
    yaml = None

if typing.TYPE_CHECKING:
    from source.core.server.manager import ServerObject

from source.core import constants
from source.core.constants import (

    # Directories
    paths,

    # General methods
    folder_check, safe_delete, run_proc, download_url, format_traceback, gen_rstring,

    # Constants
    os_name
)


# Auto-MCS Velocity Proxy Integration
# -------------------------------------------- Velocity Proxy Integration -------------------------------------------------

# Handles all methods and data relating to Velocity proxy integration
class VelocityManager():

    # Raised when Velocity has an issue being modified
    class VelocityException(BaseException):
        pass

    # Internal log wrapper
    def _send_log(self, message: str, level: str = None):
        from source.core import logger
        return logger.send_log(f'{__name__}.{self.__class__.__name__}', message, level, 'velocity')

    def __init__(self):
        # PaperMC API endpoints for Velocity
        self._api_base = "https://api.papermc.io/v2"
        self._project = "velocity"
        
        # Directory and file paths
        self.provider = 'velocity'
        self.directory = os.path.join(paths.tools, 'velocity')
        self.jar_path = None
        self.config_path = None
        self.forwarding_secret_path = None
        
        # Configuration
        self.config = {}
        self.version = None
        self.build = None
        self.port = 25577
        self.forwarding_mode = 'modern'  # 'modern' or 'legacy'
        self.forwarding_secret = None
        self.servers = {}  # {name: {address, port}}
        
        # Runtime state
        self.initialized = False
        self.service = None

    # ----- OS/filesystem handling -----
    # Check if Velocity is installed
    def _check_installed(self) -> bool:
        return self.jar_path is not None and os.path.isfile(self.jar_path)

    # Get latest Velocity version from PaperMC API
    def _get_latest_version(self) -> str:
        try:
            response = requests.get(f"{self._api_base}/projects/{self._project}")
            data = response.json()
            versions = data.get('versions', [])
            if versions:
                return versions[-1]  # Latest version
        except Exception as e:
            self._send_log(f"Failed to get latest version: {format_traceback(e)}", 'error')
        return None

    # Get latest build number for a version
    def _get_latest_build(self, version: str) -> int:
        try:
            response = requests.get(f"{self._api_base}/projects/{self._project}/versions/{version}")
            data = response.json()
            builds = data.get('builds', [])
            if builds:
                return builds[-1]  # Latest build
        except Exception as e:
            self._send_log(f"Failed to get latest build: {format_traceback(e)}", 'error')
        return None

    # Get download URL for a specific version and build
    def _get_download_url(self, version: str, build: int) -> str:
        try:
            response = requests.get(f"{self._api_base}/projects/{self._project}/versions/{version}/builds/{build}")
            data = response.json()
            application = data.get('downloads', {}).get('application', {})
            filename = application.get('name')
            if filename:
                return f"{self._api_base}/projects/{self._project}/versions/{version}/builds/{build}/downloads/{filename}", filename
        except Exception as e:
            self._send_log(f"Failed to get download URL: {format_traceback(e)}", 'error')
        return None, None

    # Download and install Velocity JAR
    def install_velocity(self, version: str = None, progress_func: callable = None) -> bool:
        
        if not constants.app_online:
            log_content = "Downloading Velocity requires an internet connection"
            self._send_log(log_content, 'error')
            raise ConnectionError(log_content)

        if self.service:
            log_content = "Can't re-install while Velocity is running"
            self._send_log(log_content, 'error')
            raise RuntimeError(log_content)

        # Get latest version if not specified
        if not version:
            version = self._get_latest_version()
            if not version:
                self._send_log("Failed to determine latest Velocity version", 'error')
                return False

        # Get latest build for version
        build = self._get_latest_build(version)
        if not build:
            self._send_log(f"Failed to determine latest build for version {version}", 'error')
            return False

        # Get download URL
        jar_url, filename = self._get_download_url(version, build)
        if not jar_url or not filename:
            self._send_log(f"Failed to get download URL for Velocity {version} build {build}", 'error')
            return False

        # Create directory structure
        folder_check(self.directory)
        
        # Delete old version if exists
        if self.jar_path and os.path.exists(self.jar_path):
            os.remove(self.jar_path)

        # Download new version
        self._send_log(f"Installing Velocity {version} build {build} from '{jar_url}'...", 'info')
        download_url(jar_url, filename, self.directory, progress_func)

        # Update paths
        self.jar_path = os.path.join(self.directory, filename)
        self.config_path = os.path.join(self.directory, 'velocity.toml')
        self.forwarding_secret_path = os.path.join(self.directory, 'forwarding.secret')
        self.version = version
        self.build = build

        success = self._check_installed()
        if success:
            self._send_log(f"Successfully installed Velocity {version} build {build}", 'info')
        else:
            self._send_log(f"Failed to install Velocity {version} build {build}", 'error')

        return success

    # Uninstall Velocity
    def uninstall_velocity(self, keep_config: bool = True) -> bool:
        
        if not self._check_installed():
            self._send_log("Can't uninstall as Velocity isn't installed")
            return True

        if self.service:
            log_content = "Can't delete while Velocity is running"
            self._send_log(log_content, 'error')
            raise RuntimeError(log_content)

        if os.path.exists(self.directory):
            self._send_log(f"Deleting Velocity from '{self.directory}'", 'info')
            if keep_config:
                if self.jar_path and os.path.exists(self.jar_path):
                    os.remove(self.jar_path)
            else:
                safe_delete(self.directory)

        return not self._check_installed()

    # Update Velocity to latest version
    def update_velocity(self) -> bool:
        success = False

        if self._check_installed():
            try:
                uninstalled = self.uninstall_velocity()
                installed = self.install_velocity()
                success = uninstalled and installed

            except Exception as e:
                self._send_log(f'Failed to update Velocity: {format_traceback(e)}', 'error')

            if success:
                self._send_log('Successfully updated Velocity', 'info')

        return success

    # Generate forwarding secret for player info forwarding
    def _generate_forwarding_secret(self) -> str:
        # Generate a 256-bit (32-byte) secret key
        secret_bytes = secrets.token_bytes(32)
        # Encode as base64
        return base64.b64encode(secret_bytes).decode('utf-8')

    # Load existing velocity.toml configuration
    def _load_config(self) -> bool:
        if os.path.exists(self.config_path):
            try:
                if toml is None:
                    self._send_log("toml library not available, cannot load config", 'warning')
                    return False
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = toml.load(f)
                self._send_log(f"Loaded Velocity configuration from '{self.config_path}'")
                return True
            except Exception as e:
                self._send_log(f"Failed to load config: {format_traceback(e)}", 'error')
        return False

    # Generate velocity.toml configuration file
    def configure_velocity(self, port: int = 25577, forwarding_mode: str = 'modern') -> bool:
        
        self.port = port
        self.forwarding_mode = forwarding_mode

        # Generate or load forwarding secret
        if os.path.exists(self.forwarding_secret_path):
            with open(self.forwarding_secret_path, 'r') as f:
                self.forwarding_secret = f.read().strip()
        else:
            self.forwarding_secret = self._generate_forwarding_secret()
            with open(self.forwarding_secret_path, 'w') as f:
                f.write(self.forwarding_secret)

        # Basic Velocity configuration
        config_content = f'''# Velocity Configuration File
# https://velocitypowered.com/wiki/

config-version = "2.7"

# Bind address - what IP and port to listen on
bind = "0.0.0.0:{port}"

# MOTD shown to players
motd = "&#09add3A Velocity Server"

# Maximum players
show-max-players = 500

# Online mode - verify players with Mojang
online-mode = true

# Force key authentication (security feature)
force-key-authentication = true

# Player info forwarding mode
# "none" - No forwarding
# "legacy" - BungeeCord-style forwarding
# "modern" - Velocity native forwarding (recommended)
player-info-forwarding-mode = "{forwarding_mode}"

# Forwarding secret for modern mode
# This MUST match the secret in your backend servers' config/paper-global.yml
forwarding-secret = "{self.forwarding_secret}"

# Server list section
[servers]
'''

        # Add configured servers
        if self.servers:
            for name, info in self.servers.items():
                config_content += f'{name} = "{info["address"]}:{info["port"]}"\n'
        else:
            # Default server
            config_content += 'lobby = "127.0.0.1:25565"\n'

        # Try order - which server to connect to first
        config_content += '\ntry = ['
        if self.servers:
            config_content += ', '.join([f'"{name}"' for name in self.servers.keys()])
        else:
            config_content += '"lobby"'
        config_content += ']\n'

        # Advanced settings
        config_content += '''
[advanced]
compression-threshold = 256
compression-level = -1
login-ratelimit = 3000
connection-timeout = 5000
read-timeout = 30000
haproxy-protocol = false

[query]
enabled = false
port = 25577
'''

        # Write configuration file
        try:
            with open(self.config_path, 'w') as f:
                f.write(config_content)
            self._send_log(f"Generated Velocity configuration at '{self.config_path}'", 'info')
            return True
        except Exception as e:
            self._send_log(f"Failed to write config: {format_traceback(e)}", 'error')
            return False

    # Add a backend server to Velocity network
    def add_server_connection(self, name: str, address: str = "127.0.0.1", port: int = 25565) -> bool:
        self.servers[name] = {"address": address, "port": port}
        self._send_log(f"Added server '{name}' at {address}:{port}")
        return True

    # Remove a backend server from Velocity network
    def remove_server_connection(self, name: str) -> bool:
        if name in self.servers:
            del self.servers[name]
            self._send_log(f"Removed server '{name}'")
            return True
        return False

    # Enable player info forwarding for a backend server
    def enable_forwarding(self, server_path: str) -> bool:
        """
        Configure a backend Paper/Spigot server to accept Velocity forwarding.
        This updates the server's paper-global.yml or spigot.yml configuration.
        """
        if yaml is None:
            self._send_log("yaml library not available, cannot configure forwarding", 'error')
            return False
            
        try:
            # For Paper servers (Paper 1.19+)
            paper_config = os.path.join(server_path, 'config', 'paper-global.yml')
            if os.path.exists(paper_config):
                with open(paper_config, 'r') as f:
                    config = yaml.safe_load(f)
                
                if 'proxies' not in config:
                    config['proxies'] = {}
                
                if self.forwarding_mode == 'modern':
                    config['proxies']['velocity'] = {
                        'enabled': True,
                        'online-mode': True,
                        'secret': self.forwarding_secret
                    }
                    config['proxies']['bungee-cord'] = {'online-mode': False}
                else:  # legacy
                    config['proxies']['bungee-cord'] = {'online-mode': True}
                    config['proxies']['velocity'] = {'enabled': False}
                
                with open(paper_config, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False)
                
                self._send_log(f"Configured Paper server for Velocity {self.forwarding_mode} forwarding", 'info')
                return True
            
            # For Spigot/BungeeCord servers (legacy)
            spigot_config = os.path.join(server_path, 'spigot.yml')
            if os.path.exists(spigot_config):
                with open(spigot_config, 'r') as f:
                    config = yaml.safe_load(f)
                
                if 'settings' not in config:
                    config['settings'] = {}
                
                config['settings']['bungeecord'] = (self.forwarding_mode == 'legacy')
                
                with open(spigot_config, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False)
                
                self._send_log(f"Configured Spigot server for BungeeCord forwarding", 'info')
                return True
            
            self._send_log(f"No compatible server config found in '{server_path}'", 'warning')
            return False
            
        except Exception as e:
            self._send_log(f"Failed to enable forwarding: {format_traceback(e)}", 'error')
            return False

    # Start Velocity proxy
    def _start_velocity(self) -> bool:
        
        if not self._check_installed():
            self._send_log("Velocity is not installed", 'error')
            return False

        if not os.path.exists(self.config_path):
            self._send_log("Velocity configuration not found, generating default...", 'warning')
            self.configure_velocity()

        if not self.service:
            # Construct Java command
            java_cmd = f'java -Xms512M -Xmx512M -XX:+UseG1GC -XX:G1HeapRegionSize=4M -XX:+UnlockExperimentalVMOptions -XX:+ParallelRefProcEnabled -XX:+AlwaysPreTouch -jar "{self.jar_path}"'
            
            self.service = subprocess.Popen(
                java_cmd,
                cwd=self.directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True
            )
            self._send_log(f"Launched Velocity proxy with PID {self.service.pid}", 'info')

        return self.service is not None and self.service.poll() is None

    # Stop Velocity proxy
    def _stop_velocity(self) -> int:
        
        if self.service and self.service.poll() is None:
            pid = self.service.pid

            # Iterate over self and children to find Velocity process
            try:
                parent = psutil.Process(self.service.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                parent = self.service

            # Kill the process tree
            try:
                for proc in parent.children(recursive=True):
                    proc.terminate()
                parent.terminate()
                
                # Wait for graceful shutdown
                try:
                    parent.wait(timeout=10)
                except psutil.TimeoutExpired:
                    # Force kill if still running
                    for proc in parent.children(recursive=True):
                        proc.kill()
                    parent.kill()
                    
            except Exception as e:
                self._send_log(f"Error stopping Velocity: {format_traceback(e)}", 'error')

            self._send_log(f"Stopped Velocity proxy with PID {pid}", 'info')

        return_code = self.service.poll() if self.service else 0
        self.service = None

        return return_code

    # Initialize Velocity manager
    def initialize(self) -> bool:
        if not self._check_installed():
            self._send_log("Velocity is not installed", 'warning')
            return False

        # Load existing configuration if available
        if os.path.exists(self.config_path):
            self._load_config()

        self.initialized = True
        self._send_log("Initialized Velocity manager", 'info')
        return self.initialized

    # Start Velocity for a server network
    def start_velocity(self) -> bool:
        if not self.initialized:
            if not self.initialize():
                return False

        return self._start_velocity()

    # Stop Velocity proxy
    def stop_velocity(self) -> bool:
        if not self.initialized:
            return False

        self._stop_velocity()
        return True

    # Get current Velocity configuration
    def get_velocity_config(self) -> dict:
        return {
            'version': self.version,
            'build': self.build,
            'port': self.port,
            'forwarding_mode': self.forwarding_mode,
            'forwarding_secret': self.forwarding_secret,
            'servers': self.servers,
            'running': self.service is not None and self.service.poll() is None
        }


# Global Velocity manager
manager: Optional[VelocityManager] = None

def init_manager():
    global manager
    if not manager:
        manager = VelocityManager()
