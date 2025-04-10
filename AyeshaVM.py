from google.cloud import compute_v1
import time

PROJECT_ID = "ayeshavm"
ZONE = "us-central1-a"
INSTANCE_NAME = "pythom-vm"
MACHINE_TYPE = "e2-standard-2"
DISK_SIZE_GB = 250
IMAGE_FAMILY = "ubuntu-2004-lts"
IMAGE_PROJECT = "ubuntu-os-cloud"

instance_client = compute_v1.InstancesClient()
address_client = compute_v1.AddressesClient()
firewall_client = compute_v1.FirewallsClient()

def wait_for_operation(operation_name, operation_type):
    operations_client = compute_v1.ZoneOperationsClient() if operation_type == "instance" else \
                       compute_v1.RegionOperationsClient() if operation_type == "address" else \
                       compute_v1.GlobalOperationsClient()
    
    while True:
        if operation_type == "instance":
            operation = operations_client.get(
                project=PROJECT_ID,
                zone=ZONE,
                operation=operation_name
            )
        elif operation_type == "address":
            operation = operations_client.get(
                project=PROJECT_ID,
                region="us-central1",
                operation=operation_name
            )
        else:
            operation = operations_client.get(
                project=PROJECT_ID,
                operation=operation_name
            )
        
        if operation.status == compute_v1.Operation.Status.DONE:
            if operation.error:
                raise Exception(f"Operation failed: {operation.error}")
            break
        time.sleep(5)

def create_instance():
    instance = compute_v1.Instance(
        name=INSTANCE_NAME,
        machine_type=f"zones/{ZONE}/machineTypes/{MACHINE_TYPE}",
        disks=[
            {
                "boot": True,
                "auto_delete": True,
                "initialize_params": {
                    "disk_size_gb": DISK_SIZE_GB,
                    "source_image": f"projects/{IMAGE_PROJECT}/global/images/family/{IMAGE_FAMILY}",
                },
            }
        ],
        network_interfaces=[
            {
                "name": "global/networks/default",
                "access_configs": [{"name": "External NAT", "type": "ONE_TO_ONE_NAT"}],
            }
        ],
        tags=compute_v1.Tags(items=["http-server", "https-server"]),
    )
    
    operation = instance_client.insert(
        project=PROJECT_ID, zone=ZONE, instance_resource=instance
    )
    print(f"Creating Virtual Machine {INSTANCE_NAME}...")
    wait_for_operation(operation.name, "instance")
    print("Virtual Machine created successfully!")

def reserve_static_ip():
    address = compute_v1.Address(
        name=f"{INSTANCE_NAME}-ip",
        region="us-central1"
    )
    operation = address_client.insert(
        project=PROJECT_ID,
        region="us-central1",
        address_resource=address
    )
    print("Reserving static IP")
    wait_for_operation(operation.name, "address")

    address = address_client.get(
        project=PROJECT_ID,
        region="us-central1",
        address=f"{INSTANCE_NAME}-ip"
    )
    print(f"Static IP reserved: {address.address}")
    return address.address

def assign_static_ip(static_ip):
    instance = instance_client.get(
        project=PROJECT_ID,
        zone=ZONE,
        instance=INSTANCE_NAME
    )
    network_interface = instance.network_interfaces[0]

    if "access_configs" in network_interface:
        operation = instance_client.delete_access_config(
            project=PROJECT_ID,
            zone=ZONE,
            instance=INSTANCE_NAME,
            access_config="External NAT",
            network_interface=network_interface.name,
        )
        wait_for_operation(operation.name, "network")

    operation = instance_client.add_access_config(
        project=PROJECT_ID,
        zone=ZONE,
        instance=INSTANCE_NAME,
        network_interface=network_interface.name,
        access_config_resource={
            "name": "External NAT",
            "nat_ip": static_ip,
            "type": "ONE_TO_ONE_NAT",
        },
    )
    wait_for_operation(operation.name, "network")
    print(f"Assigned static IP {static_ip} to {INSTANCE_NAME}")

def configure_firewall():
    firewall_rule = compute_v1.Firewall(
        name="allow-http-ssh",
        direction="INGRESS",
        allowed=[
            {"IPProtocol": "tcp", "ports": ["80"]},
            {"IPProtocol": "tcp", "ports": ["22"]},
        ],
        source_ranges=["0.0.0.0/0"],
        target_tags=["http-server", "https-server"],
    )

    operation = firewall_client.insert(
        project=PROJECT_ID,
        firewall_resource=firewall_rule
    )
    print("Configuring firewall rules")
    wait_for_operation(operation.name, "firewall")
    print("Firewall rules configured.")

def setup_web_server():
    print("To set up a web server, run manually:")
    print(f"gcloud compute ssh {INSTANCE_NAME} --zone={ZONE} --command='sudo apt update && sudo apt install -y apache2 && echo \"Hello World!\" > /var/www/html/index.html'")

if __name__ == "__main__":
    create_instance()
    static_ip = reserve_static_ip()
    assign_static_ip(static_ip)
    configure_firewall()
    setup_web_server()