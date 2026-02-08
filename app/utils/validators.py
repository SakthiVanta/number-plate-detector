import re

class IndianPlateValidator:
    """
    Forensic Validator for Indian License Plate Formats (v5.5).
    """
    
    STATE_CODES = [
        'AN','AP','AR','AS','BR','CH','CT','DN','DD','DL','GA','GJ','HR','HP','JK',
        'JH','KA','KL','LD','MP','MH','MN','ML','MZ','NL','OD','OR','PY','PB','RJ',
        'SK','TN','TG','TS','TR','UP','UK','UA','WB', 'BH'
    ]

    @staticmethod
    def is_valid(text: str) -> bool:
        """
        Validates if the text matches standard Indian plate formats.
        Format Examples:
        - TN 01 AB 1234 (Modern) -> TN01AB1234
        - 22 BH 1234 AA (Bharat Series) -> 22BH1234AA
        - TN 01 1234 (Old) -> TN011234
        """
        if not text: return False
        
        # Strip spaces and special chars
        clean_text = "".join([c for c in text if c.isalnum()]).upper()
        
        if len(clean_text) < 4 or len(clean_text) > 12:
            return False

        # 1. Bharat Series (BH) Check: 22BH1234AA
        if "BH" in clean_text:
            bh_match = re.match(r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$", clean_text)
            if bh_match: return True

        # 2. Standard State Code Check
        state_code = clean_text[:2]
        if state_code not in IndianPlateValidator.STATE_CODES:
            return False

        # 3. Standard Patterns
        patterns = [
            r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{1,4}$", # TN01AB1234
            r"^[A-Z]{2}[0-9]{1,2}[0-9]{4}$",            # TN011234 (Old style)
            r"^[A-Z]{2}[0-9]{1,3}[A-Z]{1,3}[0-9]{1,4}$" # DL10CAN1234
        ]
        
        for p in patterns:
            if re.match(p, clean_text):
                return True
                
        return False

    @staticmethod
    def get_accuracy_score(text: str) -> float:
        """
        Returns a forensic accuracy score based on pattern matching.
        """
        if not text: return 0.0
        if IndianPlateValidator.is_valid(text):
            # If it passes full validation, base score is high
            return 0.95 if len(text) >= 9 else 0.85
        return 0.3 # Low confidence if pattern fails
