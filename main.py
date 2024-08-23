import mineland

mland = mineland.make(
    task_id="techtree_1_wooden_pickaxe",
    agents_count = 1,
)

obs = mland.reset()

for i in range(5000):
    act = mineland.Action.no_op(len(obs))
    obs, code_info, event, done, task_info = mland.step(action=act)
    print(obs[0]["location_stats"]["pos"])
    if done: break

mland.close()