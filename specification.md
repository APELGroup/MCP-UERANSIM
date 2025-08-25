# MCP-UERANSIM
MCP tool to manage simulated gNB and UE resources


## Steps to achieve:
- Use this project https://github.com/aligungr/UERANSIM
  
- Upload you code here https://github.com/APELGroup/MCP-UERANSIM
  
- Keep the structure similar to this https://github.com/modelcontextprotocol/python-sdk
  
- Find or Create a container image of this project. Try minimal installation with Alpine. If not working use Ubuntu image.
  
- The installation can be found here: https://github.com/aligungr/UERANSIM/wiki/Installation. Building will add some time during building, so you can skip it for the first steps. We need it though for the final version and the image.

- In UERANSIM/config/open5gs-gnb.yaml expose:
  - linkIp, ngapIp, gtpIp
  - amfConfigs: address & port
  - Use the existing values as defaults
  - docker/nerdctl run should have them as arguments if we want to change them.

- In UERANSIM/config/open5gs-ue.yaml expose gnbSearchList

- Test that after build and run as daemons the config files are correctly setup.

- Now break the Dockerfile and the image into two separate instances, one for the gNB and on for the UE.

- In the Dockerfiles include ‘LABEL ueransim.type=gnb’ and 'LABEL ueransim.type=ue'

- Then create an MCP server using the same SDK as in the weather example with two tools: create_gnb and create_ue. This tool should create the running pods. Configurations must be done through the MCP tool. Use docker/nerdctl run in the python code. Also include --name=gnb-xxxx and --name=ue-yyyy where xxxx and yyyy will be randomly created

- Integrate this with Claude desktop or any other editor supporting MCP calls.

- Play around with the configurations.

- Add tools list_gnbs and list-ues using the above labels

- Add tools delete_gnbs and delete_ues using the names of the containers, or their IDs.

- Add tools get_gnb_logs and get_gnb_logs using the names of the containers, or their IDs. getting the specific container logs

- Add tool attach_ue_to_gnb using the name/id of UE and gNB.

  - Get the gNB container IP.
  
  - Use exec command to change the gnbSearchList with the new gNB container IP.
  
  - Use exec command to echo “success” in the logs.

- Add tool attach_gnb_to_core using the name/ID of the gNB container.

  - Two IPs must be provided as input.
  
  - Use exec command to change the ngapIp and gtpIp based on the input IPs.

- Add tool edit_exist_container using the name/ID of the container and configuration parameters.

  - Get the gNB container IP.

- Add parsing validators on all tools 

  - e.g., for the IPs that they should be in the form “x.x.x.x” only with numbers in between the dots
  
  - e.g., for the container IDs  that they should be only numbers
  
  - e.g., for the name that it should be smt like “gnb-xxxx”

  - e.g., for the existing container that it should exist and be operational

