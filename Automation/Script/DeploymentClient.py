import concurrent.futures
import json
import time

from kubernetes import client, config
from kubernetes.stream import stream

import KubernetesHelper
import Utils

YAML_FILE_TEMPLATE = '/Users/ritwik.raj/kubernetes/jupyterLab/Automation/Template/jupyterlab.yaml'
OUTPUT_PATH = '/Users/ritwik.raj/kubernetes/jupyterLab/Automation/Output'


# Todo: 1) Require function to update deployment image
# Todo: 2) Require function to delete existing deployment

class DeploymentClient:
    def __init__(self, deployment_name, namespace, replica_count, image):
        config.load_kube_config()
        self.deployment_name = deployment_name
        self.namespace = namespace
        self.replica_count = replica_count
        self.image = image

    # Function to create python custer deployment
    def create_cluster(self) -> bool:
        # Both k8s deployment and service will get create from a single yaml file
        properties_map = {'deployment_name': str(self.deployment_name), 'namespace': str(self.namespace),
                          'replica_count': str(self.replica_count), 'image': str(self.image)}
        k8s_obj_yaml = KubernetesHelper.create_k8s_yaml(
            yaml_template_file=YAML_FILE_TEMPLATE,
            properties_map=properties_map
        )

        if KubernetesHelper.create_using_yaml(k8s_obj_yaml, self.namespace):
            timeout_minutes = 1
            timeout = time.time() + 60 * timeout_minutes
            start_time = time.perf_counter()
            # Timeout in the while loop
            while True:
                running_pods = self.get_running_pods_in_cluster()
                if running_pods == int(self.replica_count):
                    print(f"INFO: Cluster {self.deployment_name} created successful")
                    Utils.Utils.write_to_yaml_file(output_path=OUTPUT_PATH, output_file_name='jupyterlab.yaml',
                                                   k8s_object_yaml=k8s_obj_yaml)
                    return True
                if time.time() > timeout:
                    # Todo: Delete the wrongly created deployment[2]
                    print(f"ERROR: Cluster {self.deployment_name} creation failed")
                    return False
                end_time = time.perf_counter()
                print(
                    f"INFO: Waiting for Deployment to become ready, {int(end_time - start_time)} seconds(s) elapsed, timeout is {1 * 60} seconds(s)...")
                time.sleep(5)
        else:
            print(f"ERROR: Cluster {self.deployment_name} creation failed")
            return False

    # Function to scale python custer deployment
    def scale_cluster(self, new_replica_count):
        if KubernetesHelper.scale_deployment(
                deployment_name=self.deployment_name,
                namespace=self.namespace,
                new_replica_count=new_replica_count):
            # Timeout in the while loop
            timeout_minutes = 1
            timeout = time.time() + 60 * timeout_minutes
            start_time = time.perf_counter()
            while True:
                running_pods = self.get_running_pods_in_cluster()
                if running_pods == int(new_replica_count):
                    print(f"INFO: Cluster {self.deployment_name} scaled successful")
                    self.replica_count = new_replica_count
                    # Todo: After successful scaling, install all python libraries in newly created pods
                    return True
                if time.time() > timeout:
                    print(f"ERROR: Cluster {self.deployment_name} scaling failed")
                    return False
                end_time = time.perf_counter()
                print(
                    f"INFO: Waiting for scaling on cluster {self.deployment_name} to become ready, {int(end_time - start_time)} seconds(s) elapsed, timeout is {1 * 60} seconds(s)...")
                time.sleep(5)
        else:
            print(f"ERROR: Cluster {self.deployment_name} scaling failed")
            return False

    # Function to execute command inside a kubernetes pod
    def exec_command_in_pod(self, pod_name, command) -> bool:
        v1 = client.CoreV1Api()
        exec_command = ["/bin/sh", "-c", command]
        resp = stream(v1.connect_get_namespaced_pod_exec,
                      pod_name,
                      self.namespace,
                      command=exec_command,
                      stderr=True, stdin=False,
                      stdout=True, tty=False,
                      _preload_content=False)

        while resp.is_open():
            resp.update(timeout=10)
            if resp.peek_stdout():
                # print(f"STDOUT: {resp.read_stdout()}")
                pass
            if resp.peek_stderr():
                print(f"STDERR: {resp.read_stderr()}")
                if "ERROR" in resp.read_stderr(): return False

        resp.close()

        if resp.returncode != 0:
            return False
        else:
            return True

    # Function to install python library in all pods of a kubernetes deployment
    def install_python_package_in_deployment(self, package) -> tuple:
        pod_status_map = self.get_pods_and_status_of_deployment()
        total_pods_count = len(pod_status_map)
        pods_package_install_count = 0
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = []
            for pod_name in pod_status_map:
                command = f"pip3 install {package}"
                if pod_status_map[pod_name] == "Running":
                    results.append(executor.submit(self.exec_command_in_pod, pod_name, command))
                else:
                    print(f"ERROR: Pod {pod_name} is not in running status")

            for f in concurrent.futures.as_completed(results):
                if f.result(): pods_package_install_count = pods_package_install_count + 1

        if pods_package_install_count == 0:
            print(
                f"ERROR: {package} package unable to install {pods_package_install_count}/{total_pods_count} Pods")
        else:
            print(
                f"INFO: {package} package is installed successfully in {pods_package_install_count}/{total_pods_count} Pods")
        return pods_package_install_count, total_pods_count

    # Check pods and status of a kubernetes deployment
    def get_pods_and_status_of_deployment(self) -> dict:
        pod_status_map = {}
        response = client.CoreV1Api().list_namespaced_pod(
            namespace=self.namespace,
            label_selector=f"app={self.deployment_name}",
            _preload_content=False
        )
        data = json.loads(response.data)
        for obj in data['items']:
            name = obj['metadata']['name']
            status = obj['status']['phase']
            pod_status_map[name] = status
        return pod_status_map

    # Function to get count of running pods in the deployment/cluster
    def get_running_pods_in_cluster(self) -> int:
        running_pods_count = 0
        pod_status_map = self.get_pods_and_status_of_deployment()
        for pod, status in pod_status_map.items():
            if status == "Running": running_pods_count = running_pods_count + 1
        return running_pods_count

    # Check python package existence in the deployment
    def check_python_package_is_present(self, package) -> dict:
        pod_status_map = self.get_pods_and_status_of_deployment()
        pod_name = list(pod_status_map.keys())[0]
        v1 = client.CoreV1Api()
        command = f"pip3 list | grep -i '{package}'"
        exec_command = ["/bin/sh", "-c", command]
        resp = stream(v1.connect_get_namespaced_pod_exec,
                      pod_name,
                      self.namespace,
                      command=exec_command,
                      stderr=True, stdin=False,
                      stdout=True, tty=False,
                      _preload_content=False)

        python_package_map = {}
        while resp.is_open():
            resp.update(timeout=10)
            if resp.peek_stdout():
                data = resp.read_stdout()
                Utils.Utils.extract_python_packages_details(data, python_package_map)

        resp.close()
        return python_package_map
