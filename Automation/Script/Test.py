import DeploymentClient
import KubernetesHelper

if __name__ == "__main__":
    obj = DeploymentClient.DeploymentClient("jupyterlab", "poc", "3", "jupyterlab:3.2")

    # m = obj.check_python_package_is_present("pand")
    # print(m)

    # obj.install_python_package_in_deployment("pandas")

    # s = obj.scale_cluster(new_replica_count=24)
    # print(s)

    # print(obj.replica_count)

    print(f"State: {obj.is_active}")

    s = obj.create_cluster()
    print(s)

    print(f"State: {obj.is_active}")

    # r = KubernetesHelper.delete_service(service_name="jupyterlab", namespace="poc")
    # print(r)

    # d = KubernetesHelper.delete_deployment(deployment_name="jupyterlab", namespace="poc")
    # print(d)

    e = obj.delete_cluster()
    print(e)
