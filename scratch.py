from automation.diffing import diff_vlans

intended = {10: "USERS", 20: "SERVERS", 30: "MANAGEMENT"}
running = {10: "SERVERS", 30: "dded"}

print(diff_vlans(intended, running))
