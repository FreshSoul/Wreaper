import reapy

project = reapy.Project()
project2 = reapy.get_projects()
region1 = reapy.Region(0)  # 当前工程

print(project2)
print(region1)
for region in project.regions:
    print(region)