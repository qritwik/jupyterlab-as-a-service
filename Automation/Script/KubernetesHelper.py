import yaml
from kubernetes import client, config, utils


def create_props_dic(properties_map):
    prop_dic = {}
    for key, value in properties_map.items():
        prop_dic["${" + key + "}"] = value
    return prop_dic


# Function to create kubernetes yaml, using template yaml file & properties map
def create_k8s_yaml(yaml_template_file=None, properties_map=None):
    props_dict = create_props_dic(properties_map=properties_map)
    with open(yaml_template_file) as f:
        data = f.read()
        if props_dict:
            for key, value in props_dict.items():
                data = data.replace(key, value)
        return yaml.safe_load_all(data)


# Function to create a kubernetes resource using yaml file
def create_using_yaml(yaml_obj, namespace) -> bool:
    try:
        config.load_kube_config()
        k8s_client = client.ApiClient()
        utils.create_from_yaml(k8s_client=k8s_client, yaml_objects=yaml_obj, verbose=True, namespace=namespace)
        return True
    except Exception as e:
        if "AlreadyExists" in str(e):
            print(f"ERROR: Cluster with same name already exists\n{e}\n")
        else:
            print(f"ERROR: Exception when calling kubectl apply: {e}\n")
        return False


# Function to delete a kubernetes service
def delete_service(service_name, namespace) -> bool:
    try:
        config.load_kube_config()
        k8s_client = client.CoreV1Api()
        k8s_client.delete_namespaced_service(name=service_name, namespace=namespace)
        return True
    except Exception as e:
        print(f"ERROR: Exception when calling delete service operation: {e}\n")
        return False


# Function to delete a kubernetes deployment
def delete_deployment(deployment_name, namespace) -> bool:
    try:
        config.load_kube_config()
        k8s_client = client.AppsV1Api()
        k8s_client.delete_namespaced_deployment(name=deployment_name, namespace=namespace)
        return True
    except Exception as e:
        print(f"ERROR: Exception when calling delete deployment operation: {e}\n")
        return False


# Function to scale a kubernetes deployment
def scale_deployment(deployment_name, namespace, new_replica_count) -> bool:
    try:
        apps_v1 = client.AppsV1Api()
        apps_v1.patch_namespaced_deployment_scale(deployment_name, namespace, {"spec": {"replicas": new_replica_count}})
        return True
    except Exception as e:
        print(f"ERROR: Exception when calling scale operation: {e}\n")
        return False
