from agents.orchestrator_agent.orchestrator import orchestrator

if __name__ == "__main__":

    user_query = input("Enter Your Goal: ")

    result = orchestrator(user_query)

    print(result)