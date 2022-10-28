import concurrent.futures
import json
import logging
import threading
import time

from kubernetes import client, config
from kubernetes.stream import stream

import KubernetesHelper
import Utils
from Automation.Constant.Constant import *

logging.basicConfig(
    filename=LOG_OUTPUT_PATH,
    level=logging.DEBUG,
    format='%(asctime)s %(lineno)d [%(threadName)s] %(levelname)s %(filename)s [%(funcName)s] %(message)s'
)


# Todo: 1) Require function to update deployment image

class DeploymentClient:
    def __init__(self, deployment_name, namespace, replica_count, image, is_active=False):
        config.load_kube_config()
        self.deployment_name = deployment_name
        self.namespace = namespace
        self.replica_count = replica_count
        self.image = image
        self.is_active = is_active

    # Function to create python custer deployment
    def create_cluster(self) -> bool:
        # Both k8s deployment and service will get created from a single yaml file
        properties_map = {'deployment_name': str(self.deployment_name), 'namespace': str(self.namespace),
                          'replica_count': str(self.replica_count), 'image': str(self.image)}
        logging.debug(f"Inputs to generate cluster k8s yaml: {properties_map}")

        k8s_obj_yaml = KubernetesHelper.create_k8s_yaml(
            yaml_template_file=YAML_FILE_TEMPLATE,
            properties_map=properties_map
        )
        logging.debug(f"Generated k8s yaml for the cluster creation: {str(k8s_obj_yaml)}")

        if KubernetesHelper.create_using_yaml(k8s_obj_yaml, self.namespace):
            logging.debug(
                f"Cluster {self.deployment_name} created, waiting for all pods to get into Running state")
            timeout_minutes = 1
            timeout = time.time() + 60 * timeout_minutes
            start_time = time.perf_counter()

            logging.debug(f"Timeout of {timeout_minutes} minute(s) before marking the cluster creation fail")
            while True:
                running_pods = self.get_running_pods_in_cluster()
                logging.debug(f"Number of pods running: {running_pods}")
                if running_pods == int(self.replica_count):
                    logging.debug(f"Cluster {self.deployment_name} created successful")
                    Utils.Utils.write_to_yaml_file(output_path=OUTPUT_PATH, output_file_name='jupyterlab.yaml',
                                                   k8s_object_yaml=k8s_obj_yaml)
                    logging.debug("Cluster creation yaml file is written to file")
                    self.is_active = True
                    return True
                if time.time() > timeout:
                    # Delete the wrongly created cluster
                    logging.debug(f"Timeout of {timeout_minutes} completed, marking the cluster creation as failed")
                    logging.debug(f"Cluster {self.deployment_name} creation failed")
                    # Creating another thread apart from main thread, to delete the wrongly created cluster
                    logging.debug("Launching another thread to delete wrongly created cluster")
                    t = threading.Thread(target=self.delete_cluster, args=[True])
                    t.start()
                    t.join()
                    return False
                end_time = time.perf_counter()
                logging.debug(
                    f"Waiting for Deployment to become ready, {int(end_time - start_time)} seconds(s) elapsed, timeout is {1 * 60} seconds(s)...")
                time.sleep(5)
        else:
            logging.debug(f"Cluster {self.deployment_name} creation failed")
            return False

    # Function to scale python custer deployment
    def scale_cluster(self, new_replica_count) -> bool:
        logging.debug(f"Scaling cluster to {new_replica_count} nodes")
        packages_list = self.get_all_python_package_present_in_cluster()
        if KubernetesHelper.scale_deployment(
                deployment_name=self.deployment_name,
                namespace=self.namespace,
                new_replica_count=new_replica_count):
            # Timeout in the while loop
            logging.debug(
                f"Cluster {self.deployment_name} scaled, waiting for all new pods to get into Running state")
            timeout_minutes = 1
            timeout = time.time() + 60 * timeout_minutes
            start_time = time.perf_counter()

            logging.debug(f"Waiting for {timeout_minutes} minute(s) before marking the cluster scaling fail")
            while True:
                running_pods = self.get_running_pods_in_cluster()
                logging.debug(f"Number of pods running: {running_pods}")
                if running_pods == int(new_replica_count):
                    logging.debug(f"Cluster {self.deployment_name} scaled successful")
                    self.replica_count = new_replica_count
                    # After successful scaling, install all python libraries in newly created pods
                    self.install_python_package_after_scaling(packages_list=packages_list)
                    return True
                if time.time() > timeout:
                    logging.debug(f"Timeout of {timeout_minutes} completed, marking the cluster scaling as failed")
                    logging.debug(f"Cluster {self.deployment_name} scaling failed")
                    return False
                end_time = time.perf_counter()
                logging.debug(
                    f"Waiting to scale cluster {self.deployment_name}, {int(end_time - start_time)} seconds(s) elapsed, timeout is {1 * 60} seconds(s)...")
                time.sleep(5)
        else:
            logging.debug(f"Cluster {self.deployment_name} scaling failed")
            return False

    # Function to install list of python packages inside a pod
    def install_python_packages_in_pod(self, pod_name, packages_list):
        total_packages = len(packages_list)
        installed_packages = 0
        logging.debug(f"{total_packages} packages needs to be installed in newly added pod {pod_name}")

        for package in packages_list:
            r = self.install_python_package_in_pod(pod_name=pod_name, package=package)
            if r:
                installed_packages = installed_packages + 1
        logging.debug(f"{installed_packages}/{total_packages} python packages installed in pod {pod_name}")

    # Function to install a python package inside a pod
    def install_python_package_in_pod(self, pod_name, package) -> bool:
        command = f"pip3 install {package}"
        logging.debug(f"Executing {command} inside the {pod_name}")
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
                logging.debug(f"{resp.read_stderr()}")
                if "ERROR" in resp.read_stderr():
                    logging.debug(f"Package installation failed inside the pod {pod_name}")
                    return False

        resp.close()

        if resp.returncode != 0:
            logging.debug(f"Package {package} installation failed inside the pod {pod_name}")
            return False
        else:
            logging.debug(f"Package {package} installation succeeded inside the pod {pod_name}")
            return True

    # Function to install python library in all pods of a kubernetes deployment
    def install_python_package_in_cluster(self, package) -> tuple:
        logging.debug(f"Installing python package {package} in the cluster {self.deployment_name}")
        pod_status_map = self.get_pods_and_status_of_deployment()
        total_pods_count = len(pod_status_map)
        pods_package_install_count = 0

        logging.debug(f"Package needs to be installed in {total_pods_count} pods")
        logging.debug(f"Creating multiple threads to install package for each pods")

        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = []
            for pod_name in pod_status_map:
                if pod_status_map[pod_name] == "Running":
                    logging.debug(f"{pod_name} is in running state, installing python package inside it")
                    results.append(executor.submit(self.install_python_package_in_pod, pod_name, package))
                else:
                    logging.debug(f"Pod {pod_name} is not in running status")

            for f in concurrent.futures.as_completed(results):
                if f.result(): pods_package_install_count = pods_package_install_count + 1

        if pods_package_install_count == 0:
            logging.debug(
                f"{package} package unable to install {pods_package_install_count}/{total_pods_count} Pods")
        else:
            logging.debug(
                f"{package} package is installed in {pods_package_install_count}/{total_pods_count} Pods")
        return pods_package_install_count, total_pods_count

    # Function to install python packages on newly launched pods after cluster scaling
    def install_python_package_after_scaling(self, packages_list) -> None:
        logging.debug(f"Python packages to be installed: {packages_list}")
        newly_launched_pods = KubernetesHelper.get_newly_launched_pods(
            deployment_name=self.deployment_name,
            namespace=self.namespace)

        logging.debug(f"Installing python packages in {len(newly_launched_pods)} newly launched pods")
        logging.debug(f"Creating multiple threads to install packages in each pods")

        with concurrent.futures.ThreadPoolExecutor() as executorPool:
            for pod_name in newly_launched_pods:
                executorPool.submit(self.install_python_packages_in_pod, pod_name, packages_list)

        logging.debug(f"Python packages are installed in {newly_launched_pods} newly launched pods")

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

    # Function to get python package in the cluster, based upon a package name
    def get_python_package_present_in_cluster(self, package="") -> dict:
        if package == "":
            logging.debug(f"Searching for all python packages in the cluster {self.deployment_name}")
        else:
            logging.debug(f"Searching for python package {package} in the cluster {self.deployment_name}")
        pod_status_map = self.get_pods_and_status_of_deployment()
        pod_name = list(pod_status_map.keys())[0]
        if package == "":
            logging.debug(f"All packages to be searched in pod {pod_name}")
        else:
            logging.debug(f"{package} to be searched in pod {pod_name}")
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
        if package == "":
            logging.debug(f"Packages found: {python_package_map}")
        else:
            logging.debug(f"Package searched: {package}, Matching packages found: {python_package_map}")
        return python_package_map

    # Function to get all python packages in the cluster
    def get_all_python_package_present_in_cluster(self) -> list:
        packages_list = []
        python_package_map = self.get_python_package_present_in_cluster()
        for name in python_package_map:
            packages_list.append(f"{name}=={python_package_map[name]}")
        return packages_list

    # Function to delete the entire cluster
    def delete_cluster(self, skip_is_active_check=False) -> bool:
        if self.is_active or skip_is_active_check:
            logging.debug("Cluster is active, deleting it!!")
            response_dep, response_svc = False, False
            with concurrent.futures.ThreadPoolExecutor() as executor:
                response_dep = executor.submit(KubernetesHelper.delete_deployment, self.deployment_name, self.namespace)
                response_svc = executor.submit(KubernetesHelper.delete_service, self.deployment_name, self.namespace)
            if response_dep and response_svc:
                self.is_active = False
                logging.debug(f"Cluster {self.deployment_name} is deleted successfully")
                return True
            else:
                logging.debug(f"Error while deleting the cluster {self.deployment_name}")
                return False
        else:
            logging.debug(f"Cluster {self.deployment_name} is already in inactive state")
            return False
