'''
This script demonstrates how to run the Alex agent in the mineland environment.

Please set your key in OPENAI_API_KEY environment variable before running this script.
Or, you can set the key in the script as follows (not recommended):
'''
import os
os.environ["OPENAI_API_KEY"] = "" # set your key here

import mineland
from mineland.alex import Alex

mland = mineland.make(
    task_id="survival_chat_with_partner_agent",
    agents_count = 2,
)

# initialize agents
agents = []
alex = Alex(personality='None',             # Alex configuration
            llm_model_name='gpt-4o',
            vlm_model_name='gpt-4o',
            bot_name='MineflayerBot0',
            temperature=0.1)
# jennifer = Alex(personality='None',             # Jenniger configuration
#             llm_model_name='gpt-4o',
#             vlm_model_name='gpt-4o',
#             bot_name='MineflayerBot1',
#             temperature=0.1)
agents.append(alex)
# agents.append(jennifer)

obs = mland.reset()

agents_count = len(obs)
agents_name = [obs[i]['name'] for i in range(agents_count)]

for i in range(5000):
    if i > 0 and i % 10 == 0:
        print("task_info: ", task_info)
    actions = []
    if i == 0:
        # skip the first step which includes respawn events and other initializations
        actions = mineland.Action.no_op(agents_count)
    else:
        # run agents
        for idx, agent in enumerate(agents):
            action = agent.run(obs[idx], code_info[idx], done, task_info, verbose=True)
            exit()
            actions.append(action)

    obs, code_info, event, done, task_info = mland.step(action=actions)
    if i % 10 == 0:
        print("Position", obs[0]["location_stats"]["pos"])
