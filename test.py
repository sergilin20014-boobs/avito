import pathlib

def merge_python_files(directory_path, output_filename='merged_code.txt'):
    root_dir = pathlib.Path(directory_path)
    
    with open(output_filename, 'w', encoding='utf-8') as outfile:
        # rglob('*') найдет все файлы, включая скрытые (начинающиеся с точки)
        for file_path in root_dir.rglob('*.py'):
            
            # Пропускаем, если в пути есть .venv или __pycache__
            if '.venv' in file_path.parts or '__pycache__' in file_path.parts:
                continue
                
            # Пропускаем сам выходной файл
            if file_path.name == output_filename:
                continue
                
            try:
                content = file_path.read_text(encoding='utf-8')
                
                outfile.write(f"\n{'='*30}\n")
                outfile.write(f"PATH: {file_path.relative_to(root_dir)}\n")
                outfile.write(f"{'='*30}\n\n")
                outfile.write(content)
                outfile.write("\n")
                
                print(f"Добавлен: {file_path.relative_to(root_dir)}")
            except Exception as e:
                print(f"Не удалось прочитать {file_path}: {e}")

if __name__ == "__main__":
    # Запускаем в текущей директории
    merge_python_files('.')