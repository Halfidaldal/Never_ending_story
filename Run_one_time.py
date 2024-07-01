import uuid

# Function to get a unique system identifier
def get_system_id():
    return uuid.uuid1()

# Function to save the system ID to a text file
def save_system_id_to_file(system_id, filename):
    with open(filename, 'w') as file:
        file.write(f'{system_id}')

# Main function to execute the script
def main():
    # Generate a unique system ID
    system_id = get_system_id()
    
    # Define the static filename
    filename = 'system_id.txt'
    
    # Save the system ID to the text file
    save_system_id_to_file(system_id, filename)
    
    print(f'System ID saved to file: {filename}')

# Run the script
if __name__ == "__main__":
    main()
