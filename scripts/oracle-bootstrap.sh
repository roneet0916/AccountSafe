#!/usr/bin/env bash
# =============================================================================
# AccountSafe - Oracle Cloud VM Bootstrap
# =============================================================================
# Run this ONCE on a fresh Ubuntu 22.04 LTS (ARM or x86) Oracle Cloud instance.
# It installs Docker + Compose plugin, configures swap, opens the firewall,
# hardens SSH, and sets up fail2ban.
#
# Usage (on the VM, as the `ubuntu` user):
#   curl -fsSL https://raw.githubusercontent.com/<your-org>/AccountSafe/main/scripts/oracle-bootstrap.sh -o bootstrap.sh
#   chmod +x bootstrap.sh && ./bootstrap.sh
#
# Or after `git clone`:
#   chmod +x scripts/oracle-bootstrap.sh && ./scripts/oracle-bootstrap.sh
# =============================================================================

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[bootstrap]${NC} $*"; }
warn() { echo -e "${YELLOW}[bootstrap]${NC} $*"; }
die()  { echo -e "${RED}[bootstrap]${NC} $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] && die "Run as the 'ubuntu' user, not root. The script uses sudo where needed."
command -v sudo >/dev/null || die "sudo is required."

# -----------------------------------------------------------------------------
# 1. System update
# -----------------------------------------------------------------------------
log "Updating apt packages..."
sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates curl gnupg lsb-release git ufw fail2ban unattended-upgrades \
    htop jq netcat-openbsd

# -----------------------------------------------------------------------------
# 2. Swap (Oracle free tier VMs have no swap by default; Postgres + Django
#    builds can OOM under memory pressure.)
# -----------------------------------------------------------------------------
if ! swapon --show | grep -q '/swapfile'; then
    log "Creating 4G swap file..."
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
    echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-swappiness.conf >/dev/null
    sudo sysctl -p /etc/sysctl.d/99-swappiness.conf
else
    log "Swap already configured, skipping."
fi

# -----------------------------------------------------------------------------
# 3. Docker Engine + Compose plugin (official Docker repo, ARM + x86 compatible)
# -----------------------------------------------------------------------------
if ! command -v docker >/dev/null; then
    log "Installing Docker Engine..."
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    ARCH="$(dpkg --print-architecture)"
    CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"
    echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $CODENAME stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker "$USER"
    warn "You were added to the 'docker' group. Log out + back in (or run 'newgrp docker') before using docker without sudo."
else
    log "Docker already installed, skipping."
fi

# -----------------------------------------------------------------------------
# 4. Firewall
#    Oracle Cloud Ubuntu images ship with an iptables REJECT rule on INPUT that
#    blocks ports other than 22. We flush that and rely on ufw instead. The OCI
#    VCN Security List ingress rules must ALSO permit 80/443 (done in the OCI
#    console; this script cannot change cloud-level firewalls).
# -----------------------------------------------------------------------------
log "Configuring ufw firewall..."
sudo ufw --force reset >/dev/null
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp   comment 'SSH'
sudo ufw allow 80/tcp   comment 'HTTP (ACME + redirect)'
sudo ufw allow 443/tcp  comment 'HTTPS'
sudo ufw --force enable

# Remove Oracle's default REJECT rule if present.
if sudo iptables -S INPUT | grep -q 'REJECT --reject-with icmp-host-prohibited'; then
    warn "Removing Oracle's default iptables INPUT REJECT rule..."
    sudo iptables -D INPUT -j REJECT --reject-with icmp-host-prohibited || true
    sudo netfilter-persistent save 2>/dev/null || \
        sudo sh -c 'iptables-save > /etc/iptables/rules.v4' 2>/dev/null || true
fi

# -----------------------------------------------------------------------------
# 5. Fail2ban (SSH brute-force protection)
# -----------------------------------------------------------------------------
log "Configuring fail2ban..."
sudo tee /etc/fail2ban/jail.d/sshd.local >/dev/null <<'EOF'
[sshd]
enabled  = true
port     = ssh
maxretry = 5
findtime = 10m
bantime  = 1h
EOF
sudo systemctl enable --now fail2ban

# -----------------------------------------------------------------------------
# 6. Unattended security updates
# -----------------------------------------------------------------------------
log "Enabling unattended security upgrades..."
sudo dpkg-reconfigure -f noninteractive unattended-upgrades

# -----------------------------------------------------------------------------
# 7. Summary + next steps
# -----------------------------------------------------------------------------
log "Bootstrap complete."
echo
echo "Next steps:"
echo "  1. In the Oracle Cloud console -> VCN -> Security List, add ingress rules"
echo "     for TCP/80 and TCP/443 from 0.0.0.0/0 (if not already present)."
echo "  2. Point your DNS (DuckDNS/sslip.io/custom) at this VM's public IP."
echo "  3. Log out + back in so the docker group takes effect, then:"
echo "       git clone <your-repo> AccountSafe && cd AccountSafe"
echo "       cp .env.oracle.example .env && nano .env"
echo "       make oracle-ssl-init"
echo "       make oracle-up"
