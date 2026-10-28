user_input = input("Whar did she say? ")


decoded_text = user_input.replace("###", "o")
decoded_text = decoded_text.replace("##", "e")
decoded_text = decoded_text.replace("%%", "a")

print(f"She meant to say: {decoded_text}")