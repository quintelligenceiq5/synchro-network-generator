**# Synchro Network Generator - Streamlit App**



**## 🚀 Deployment Guide**



**### Step 1: Create GitHub Repository**



**1. Go to https://github.com/quintelligenceiq5**

**2. Click "+" → "New repository"**

**3. Repository name: `synchro-network-generator`**

**4. Description: `Web app for generating Synchro traffic network files`**

**5. Choose "Public" (required for free Streamlit hosting)**

**6. Click "Create repository"**



**### Step 2: Upload Files to GitHub**



**\*\*Option A: Using GitHub Web Interface (Easiest)\*\***



**1. On your new repository page, click "uploading an existing file"**

**2. Upload these files:**

   **- `streamlit\_app.py` (the main app code)**

   **- `requirements.txt`**

   **- `.gitignore`**

   **- `README.md` (this file)**

**3. Click "Commit changes"**



**\*\*Option B: Using Git Command Line\*\***



**```bash**

**# On your computer**

**git clone https://github.com/quintelligenceiq5/synchro-network-generator.git**

**cd synchro-network-generator**



**# Copy the 4 files into this folder**

**# Then:**

**git add .**

**git commit -m "Initial commit"**

**git push**

**```**



**### Step 3: Deploy to Streamlit Cloud**



**1. Go to https://streamlit.io/cloud**

**2. Click "New app"**

**3. Connect your GitHub account (if not already)**

**4. Select:**

   **- \*\*Repository\*\*: `quintelligenceiq5/synchro-network-generator`**

   **- \*\*Branch\*\*: `main`**

   **- \*\*Main file path\*\*: `streamlit\_app.py`**

**5. Click "Advanced settings" → "Secrets"**



**### Step 4: Add Secrets (IMPORTANT!)**



**In the Secrets section, paste this EXACT format:**



**```toml**

**\[google\_credentials]**

**type = "service\_account"**

**project\_id = "synchro-file-storage"**

**private\_key\_id = "62c0e5879c0571ca17dedb38d02a555e76e14481"**

**private\_key = "-----BEGIN PRIVATE KEY-----\\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC09604OUX6/JYp\\ntTuR6f2Sxb+9eNGMU1U2VUzY2cJGJpN7F14DHtIVlAUhEaY9G2BTWYHYSdjYF8eC\\nbmXZHYh3RK7lGQ5trLCsMQdjt0dyPy32hTqSjFIMmXjjwZF2yF5dB7uIhlSUlSex\\n+sjWlgotgyupOsJG3NlcrwEL4ZFKCzk0wI8Wvr8R0HUr1ucEsBCX+F0+iDdHJfX1\\nLhV1yQOO5Ch018z9gB2kYt1Yc1EFKzIwglmKcOZrm3S5x926ns9vkDR+sYnziEJN\\nEVr40X73RZct68/SobiW65PRCunnWYL7TaL02pZSjaZLsOcpCiaQgDY/7D8U+1F6\\n2REoU1HzAgMBAAECggEAJZTR6j0qpUbTQHIcnt7DBDoA6a4vhj7AEXqBbP878ymL\\nsyJVKby60DRfJFDv/vyyclzCNFKRr76wdgvLJt2VO3+N+pHLh0c3oWrFKBYlxjoM\\np4dfdJOjbm5oxpOqS8qsnhE/Bskuw3R+O93i231pO65j4M8NDX5LvY2yX+9GJuP4\\nJcamkbSw2HLBnApk/vatyeW/AsJKP4gWCDlrulwoOWhIKJwDuFMpIcTj0WSbASff\\n8PVVHvKZ78uGk556+UP+6nAXvTAfqku3oPqTwYina84FSECRBrGM9R+4R+WAc0V/\\nNXKMPhVzAAmUe68ux5IvlozvblfWEoR0kO1UPCKRUQKBgQDn5lYnLxbl9TOvD1C4\\nxE5rQIU1kl/BTUcxrXGMyzZ7ZGTv51zzmndXWMOpUhRIn0RRSOceix7dmvgy6kmk\\nPSWBHIgfan6koQ5wJ+3aBe8Aj9HFWBActRJKO806rbXki0VHKsDW0jjI7Xnu7qeB\\nqDOrOx53IbSxvxaenQNzMxQHDwKBgQDHxkss35TXBXJDSzWxeuK90ixM8Z3aH0uR\\n+izxBtE7gYBITGUi9sllaHAci4kyWSHh+uGTxhtIFVdCRy2YVVp0YxN6SeJfzZQB\\nYcb72WigZ0Za4LIH7GsiikfQ40U22i4k9j/L3C08rsMzci9iJBZ8+ZSlXMEUrvdW\\naOCxYTMm3QKBgQC1VdFCnLjsItxCZNh7Us37Yh2IMah88F/egcEMFo/I101yp1lx\\nB/WQMNH3Yj6INzpl0Xsg0CrXoOm6bqgdLM9Z8aSj5FOZinNO0npUhVVJ/CxNg7o9\\nqH3f3Hl0DAfy6dDHgLAAi6xpugEiDC6h3ZRhrj35bDruzvzyFNdwyp07kwKBgBlO\\nh0th70rlx7m6l0yqUnrVWwNMQEDXYg1V8cd+o5a0Kvn9o3owZQbRmhIjovebzuz/\\niP/dQqt4+JrOxXncph7ERj1hiqm0MyGRr1FMEzLuojz05diXHGM9vSc7AxOVw+6u\\nuxoqBBkB0nx75IC8LZUbULc57sOd/nsVwhD2TTKJAoGAEj+TeDTcEG7mK/ac+Qi9\\nl/Ex8baP2ucg4PMyryGYMQpbWrqTwqPYGP48WPvB+ISu4NhZvbhHvqcNNc7eGedt\\nXWVEN8fidsFBaDgsI4GjrzyisE18WNNtKYysATsINBQkuInZis+Z9OzM4RYdiKgY\\n8AT+yhL6hFM9WmZdm38JKIw=\\n-----END PRIVATE KEY-----\\n"**

**client\_email = "synchro-app-service@synchro-file-storage.iam.gserviceaccount.com"**

**client\_id = "118133554181136860031"**

**auth\_uri = "https://accounts.google.com/o/oauth2/auth"**

**token\_uri = "https://oauth2.googleapis.com/token"**

**auth\_provider\_x509\_cert\_url = "https://www.googleapis.com/oauth2/v1/certs"**

**client\_x509\_cert\_url = "https://www.googleapis.com/robot/v1/metadata/x509/synchro-app-service%40synchro-file-storage.iam.gserviceaccount.com"**

**universe\_domain = "googleapis.com"**



**google\_drive\_folder\_id = "1aPfNe1RZFn\_0oI23FE3CFnyS5guhHnVz"**

**google\_sheet\_id = "1ThWuL08\_1T4clxpH0HRFqKrcV3dZfOHcCBjOBaj0Mpg"**

**```**



**### Step 5: Deploy!**



**1. Click "Deploy!"**

**2. Wait 2-3 minutes for deployment**

**3. You'll get a URL like: `https://quintelligenceiq5-synchro-network-generator-streamlit-app-xxxxx.streamlit.app`**



**### Step 6: Share with Team**



**Share the URL with your team! They can:**

**- Generate Synchro files**

**- Download .txt and .csv files**

**- Files automatically backup to your Google Drive**



**---**



**## 🔄 Updating the App**



**When you want to add features or fix bugs:**



**1. Edit `streamlit\_app.py` on your computer**

**2. Push to GitHub:**

   **```bash**

   **git add streamlit\_app.py**

   **git commit -m "Added new feature"**

   **git push**

   **```**

**3. Streamlit automatically redeploys (1-2 minutes)**

**4. \*\*Same URL, updated app!\*\***



**---**



**## 📁 Where Files Are Saved**



**- \*\*User downloads\*\*: To their computer**

**- \*\*Your backup\*\*: Google Drive folder: `Synchro\_Generated\_Files`**

**- \*\*Usage log\*\*: Google Sheet: `Synchro Usage Log`**



**---**



**## 🆘 Troubleshooting**



**### App won't deploy**

**- Check that all 4 files are in GitHub**

**- Verify secrets are pasted correctly (no extra spaces)**



**### Google Drive not working**

**- Verify service account email is shared with your Drive folder**

**- Check folder ID is correct**



**### Google Sheets not logging**

**- Verify service account has access to the sheet**

**- Check sheet ID is correct**



**---**



**## 📞 Support**



**For issues, check:**

**- Streamlit logs in the dashboard**

**- Google Cloud Console for API errors**

**- This README for setup steps**



**---**



**## 🎉 You're Done!**



**Your app is now live and accessible to your team!**

