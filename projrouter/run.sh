# För att skriva /etc/nginx och /etc/systemd behöver du sudo
sudo python3 main.py --registry /home/<user>/servers/registry.toml activate projekt1 9001
sudo python3 main.py --registry /home/<user>/servers/registry.toml check
sudo python3 main.py --registry /home/<user>/servers/registry.toml deactivate projekt1

