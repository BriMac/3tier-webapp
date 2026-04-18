Vagrant.configure("2") do |config|
  config.vm.box = "generic/debian12"

  nodes = {
    "web01" => { ip: "10.10.10.10", mem: 1024 },
    "app01" => { ip: "10.10.10.11", mem: 2048 },
    "app02" => { ip: "10.10.10.12", mem: 2048 },
    "db01"  => { ip: "10.10.10.20", mem: 2048 }
  }

 config.vm.synced_folder ".", "/vagrant", type: "rsync"

  nodes.each do |name, cfg|
    config.vm.define name do |node|
      node.vm.hostname = name
      node.vm.network "private_network", ip: cfg[:ip], libvirt__network_name: "3tier-net"
      node.vm.provider :libvirt do |lv|
        lv.memory = cfg[:mem]
        lv.cpus = 2
      end
      node.vm.provision "shell", path: "provision/install-docker.sh"
    end
  end
end
 
