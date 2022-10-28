import DeploymentClient
import KubernetesHelper

if __name__ == "__main__":
    obj = DeploymentClient.DeploymentClient("jupyterlab", "poc", "1", "jupyterlab:3.2")


    # obj.install_python_package_in_cluster("pandas==1.5.1")

    s = obj.scale_cluster(new_replica_count=10)
    print(s)

    # print(obj.replica_count)

    # print(f"State: {obj.is_active}")

    # s = obj.create_cluster()
    # print(s)

    # print(f"State: {obj.is_active}")

    # r = KubernetesHelper.delete_service(service_name="jupyterlab", namespace="poc")
    # print(r)
    #
    # d = KubernetesHelper.delete_deployment(deployment_name="jupyterlab", namespace="poc")
    # print(d)
    #
    # e = obj.delete_cluster()
    # print(e)

    # print(f"State: {obj.is_active}")

    # u = KubernetesHelper.get_newly_launched_pods("jupyterlab", "poc")
    # print(u)

    # m = obj.get_python_package_present_in_cluster("pan")
    # print(m)

    # d = obj.get_all_python_package_present_in_cluster()
    # print(d)