import DeploymentClient


if __name__ == "__main__":
    obj = DeploymentClient.DeploymentClient("jupyterlab", "poc", "3", "jupyterlab:3.2")
    # m = obj.check_python_package_is_present("pand")
    # print(m)

    # obj.install_python_package_in_deployment("pandas")

    s = obj.scale_cluster(new_replica_count=24)
    print(s)
    #
    print(obj.replica_count)

    # s = obj.create_cluster()
    # print(s)

