import os
import yaml

class Utils:
    def __init__(self):
        pass

    # Function to write json data to file
    @staticmethod
    def write_to_file(data, output_file_name):
        save_path = '/Users/ritwik.raj/kubernetes/jupyterLab/Automation/Output'
        completeName = os.path.join(save_path, output_file_name)
        output_file = open(completeName, "w")
        output_file.write(data)
        output_file.close()

    # Function to extract python package and version from complex object
    @staticmethod
    def extract_python_packages_details(data, python_package_map):
        packages_version_list = data.split("\n")
        for ctr, temp in enumerate(packages_version_list):
            package_version_list = temp.split(" ")
            package_name = str(package_version_list[0])
            package_version = str(package_version_list[len(package_version_list) - 1])
            if package_name != "Package" and package_name != "" and package_name.isalpha() and package_version != "":
                python_package_map[package_name] = package_version

    @staticmethod
    def write_to_yaml_file(output_path, output_file_name, k8s_object_yaml):
        output_file_name = f"{output_path}/{output_file_name}"
        with open(output_file_name, 'w') as outfile:
            yaml.dump_all(k8s_object_yaml, outfile)
