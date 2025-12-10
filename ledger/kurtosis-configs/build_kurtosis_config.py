import yaml
import sys
from pathlib import Path

path = Path(__file__).parent

def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_yaml.py num_participants")
        sys.exit(1)
        
    count_participants = int(sys.argv[1])
    
    participant = []
    
    with open(path.joinpath("templates", "participant.template.yaml"), 'r') as pt:
        participant = yaml.safe_load(pt)
        participants = [participant.copy() for _ in range(count_participants)]
    
    network_config = None
    with open(path.joinpath("templates", "network.parameters.yaml"), 'r') as net_params:
        network_config = yaml.safe_load(net_params)
    
    final_config = {
        'participants': participants,
        **network_config  # Merge other top-level configs
    }
    
    with open(path.joinpath("kurtosis-eth-net.yaml"), 'w') as out:
        yaml.dump(final_config, out, default_flow_style=False, sort_keys=False)
        
    print("wrote kurtosis config")
    
main()