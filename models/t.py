import os

if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))
    father_path = os.path.dirname(current_dir)
    print(current_dir)
    print(father_path)
