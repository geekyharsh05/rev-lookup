"""
LinkedIn Profile Data Mapper for profile_database table
Maps data from linkedin_profiles table structure to profile_database table structure
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid

class LinkedInProfileMapper:
    """Maps LinkedIn API response to DynamoDB profile_database table structure"""
    
    @staticmethod
    def map_profile_data(profile_response: Dict, email: str) -> Dict:
        """
        Map LinkedIn API response to profile_database table structure
        
        Args:
            profile_response: Response from LinkedIn API (from linkedin_profiles table)
            email: Email used for the query
            
        Returns:
            Formatted profile data for profile_database table
        """
        try:
            # Handle both direct API response and linkedin_profiles table format
            if 'profile_data' in profile_response:
                # Data from linkedin_profiles table
                profile_data = profile_response['profile_data']
                if isinstance(profile_data, dict) and 'M' in profile_data:
                    # DynamoDB format - extract the actual data
                    data = LinkedInProfileMapper._extract_from_dynamodb_format(profile_data['M'])
                else:
                    data = profile_data
            else:
                # Direct API response
                data = profile_response.get('data', profile_response)
            
            # Extract person data from the API response
            persons = data.get('persons', {})
            if isinstance(persons, dict) and 'L' in persons:
                # DynamoDB list format
                persons_list = [LinkedInProfileMapper._extract_from_dynamodb_format(p['M']) for p in persons['L']]
            else:
                persons_list = persons if isinstance(persons, list) else []
            
            # Get the first (main) profile
            profile = persons_list[0] if persons_list else {}
            
            # Extract LinkedIn URL and ID
            linkedin_url = profile.get('linkedInUrl', '')
            linkedin_id = LinkedInProfileMapper._extract_linkedin_id(linkedin_url)
            
            # Build the mapped profile
            mapped_profile = {
                "id": {"S": linkedin_id or email.replace('@', '_at_').replace('.', '_')},
                "url": {"S": linkedin_id or ""},
                "linkedin_id": {"S": linkedin_id or ""},
                "linkedin_num_id": {"S": LinkedInProfileMapper._extract_numeric_id_from_urn(profile.get('id', ''))},
                "input": {
                    "M": {
                        "url": {"S": linkedin_url or ""},
                        "email": {"S": email}
                    }
                },
                "input_url": {"S": linkedin_url or ""},
                "timestamp": {"S": datetime.now().isoformat()},
                "created_at": {"S": datetime.now().isoformat()},
                "updated_at": {"S": datetime.now().isoformat()},
                "updated_by": {"S": "outlook-login-system"},
                
                # Personal Information
                "name": {"S": profile.get('displayName', '')},
                "first_name": {"S": profile.get('firstName', '')},
                "last_name": {"S": profile.get('lastName', '')},
                "position": {"S": profile.get('headline', '')},
                "about": {"S": profile.get('summary', '')},
                "location": {"S": profile.get('location', '')},
                "city": {"S": LinkedInProfileMapper._extract_city_from_location(profile.get('location', ''))},
                "country_code": {"S": LinkedInProfileMapper._extract_country_code_from_locale(profile.get('locale', {}))},
                
                # Profile Images
                "avatar": {"S": profile.get('photoUrl', '')},
                "banner_image": {"S": "https://static.licdn.com/aero-v1/sc/h/5q92mjc5c51bjlwaj3rs9aa82"},  # Default LinkedIn banner
                "default_avatar": {"BOOL": not bool(profile.get('photoUrl', ''))},
                
                # Connection Info (set defaults since API doesn't provide this)
                "connections": {"N": "500"},  # Default as API doesn't provide
                "followers": {"N": "0"},  # Default as API doesn't provide
                
                # Current Company
                "current_company": LinkedInProfileMapper._extract_current_company_from_positions(profile),
                "current_company_name": {"S": profile.get('companyName', '')},
                "current_company_company_id": {"S": LinkedInProfileMapper._extract_company_id_from_positions(profile)},
                
                # Experience
                "experience": LinkedInProfileMapper._extract_experience_from_positions(profile),
                
                # Education
                "education": LinkedInProfileMapper._extract_education_from_schools(profile),
                "educations_details": {"S": LinkedInProfileMapper._extract_primary_education(profile)},
                
                # Skills & Certifications (empty as API doesn't provide detailed info)
                "certifications": {"L": []},
                "courses": {"L": []},
                "languages": {"L": []},
                "patents": {"L": []},
                "publications": {"L": []},
                "projects": {"L": []},
                "organizations": {"L": []},
                
                # Activity & Recommendations (empty as API doesn't provide)
                "activity": {"L": []},
                "posts": {"L": []},
                "recommendations": {"L": []},
                "recommendations_count": {"N": "0"},
                
                # Awards & Honors (empty as API doesn't provide)
                "honors_and_awards": {"L": []},
                
                # Volunteer Experience (empty as API doesn't provide)
                "volunteer_experience": {"L": []},
                
                # Related Profiles (empty as API doesn't provide)
                "people_also_viewed": {"L": []},
                "similar_profiles": {"L": []},
                
                # Bio and Additional Info
                "bio_links": {"L": []},
                
                # Account Status
                "memorialized_account": {"BOOL": False},
                
                # Snapshot tracking
                "snapshot_id": {"S": str(uuid.uuid4())},
                "snapshotid": {"S": str(uuid.uuid4())},
                "new_snapshot_id": {"S": str(uuid.uuid4())},
                
                # User ID (derived from email)
                "user_id": {"S": email.replace('@', '_at_').replace('.', '_')}
            }
            
            return mapped_profile
            
        except Exception as e:
            print(f"❌ Error mapping profile data for {email}: {e}")
            import traceback
            traceback.print_exc()
            
            # Return minimal structure with error info
            return LinkedInProfileMapper._create_empty_profile_structure(email, str(e))
    
    @staticmethod
    def _extract_from_dynamodb_format(dynamo_data: Dict) -> Dict:
        """Extract data from DynamoDB format recursively"""
        if not isinstance(dynamo_data, dict):
            return dynamo_data
        
        result = {}
        for key, value in dynamo_data.items():
            if isinstance(value, dict):
                if 'S' in value:  # String
                    result[key] = value['S']
                elif 'N' in value:  # Number
                    try:
                        result[key] = int(value['N'])
                    except ValueError:
                        result[key] = float(value['N'])
                elif 'BOOL' in value:  # Boolean
                    result[key] = value['BOOL']
                elif 'L' in value:  # List
                    result[key] = [LinkedInProfileMapper._extract_from_dynamodb_format(item) for item in value['L']]
                elif 'M' in value:  # Map
                    result[key] = LinkedInProfileMapper._extract_from_dynamodb_format(value['M'])
                else:
                    result[key] = value
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def _extract_linkedin_id(url: str) -> str:
        """Extract LinkedIn ID from URL"""
        if not url:
            return ""
        
        # Handle different URL formats
        if "/in/" in url:
            return url.split("/in/")[-1].split("/")[0].split("?")[0]
        elif "/pub/" in url:
            return url.split("/pub/")[-1].split("/")[0]
        
        return ""
    
    @staticmethod
    def _extract_numeric_id_from_urn(urn: str) -> str:
        """Extract numeric ID from LinkedIn URN"""
        if not urn or 'urn:li:person:' not in urn:
            return ""
        
        # Extract the hash after urn:li:person:
        return urn.split('urn:li:person:')[-1]
    
    @staticmethod
    def _extract_city_from_location(location: str) -> str:
        """Extract city from location string"""
        if not location:
            return ""
        
        # Location format: "Bengaluru, Karnataka, India"
        parts = [part.strip() for part in location.split(',')]
        return parts[0] if parts else ""
    
    @staticmethod
    def _extract_country_code_from_locale(locale: Dict) -> str:
        """Extract country code from locale object"""
        if isinstance(locale, dict):
            return locale.get('country', '').upper()
        return ""
    
    @staticmethod
    def _extract_current_company_from_positions(profile: Dict) -> Dict:
        """Extract current company information from positions"""
        positions = profile.get('positions', {})
        position_history = positions.get('positionHistory', [])
        
        if position_history:
            # Get the first position (most recent)
            current_position = position_history[0]
            company_info = current_position.get('company', {})
            
            company_name = company_info.get('companyName', current_position.get('companyName', ''))
            company_url = company_info.get('linkedInUrl', '')
            company_id = LinkedInProfileMapper._extract_company_id_from_url(company_url)
            
            return {
                "M": {
                    "name": {"S": company_name},
                    "title": {"S": company_name},
                    "company_id": {"S": company_id},
                    "link": {"S": company_url}
                }
            }
        
        return {"M": {"name": {"S": ""}, "title": {"S": ""}, "company_id": {"S": ""}, "link": {"S": ""}}}
    
    @staticmethod
    def _extract_company_id_from_positions(profile: Dict) -> str:
        """Extract company ID from current position"""
        current_company = LinkedInProfileMapper._extract_current_company_from_positions(profile)
        return current_company.get("M", {}).get("company_id", {}).get("S", "")
    
    @staticmethod
    def _extract_company_id_from_url(url: str) -> str:
        """Extract company ID from LinkedIn company URL"""
        if not url or "/company/" not in url:
            return ""
        
        return url.split("/company/")[-1].split("/")[0].split("?")[0]
    
    @staticmethod
    def _extract_experience_from_positions(profile: Dict) -> Dict:
        """Extract work experience from positions"""
        positions = profile.get('positions', {})
        position_history = positions.get('positionHistory', [])
        
        if not position_history:
            return {"L": []}
        
        # Group positions by company
        companies = {}
        
        for position in position_history:
            company_info = position.get('company', {})
            company_name = company_info.get('companyName', position.get('companyName', ''))
            
            if company_name not in companies:
                companies[company_name] = {
                    "company_info": company_info,
                    "positions": []
                }
            
            companies[company_name]["positions"].append(position)
        
        # Build experience list
        experience_list = []
        for company_name, company_data in companies.items():
            company_info = company_data["company_info"]
            positions_list = company_data["positions"]
            
            # Calculate total duration at company
            total_duration = LinkedInProfileMapper._calculate_total_duration_at_company(positions_list)
            
            experience_item = {
                "M": {
                    "company": {"S": company_name},
                    "company_id": {"S": LinkedInProfileMapper._extract_company_id_from_url(company_info.get('linkedInUrl', ''))},
                    "title": {"S": company_name},
                    "url": {"S": company_info.get('linkedInUrl', '')},
                    "duration": {"S": total_duration},
                    "location": {"S": company_info.get('companyLocation', '')},
                    "company_logo_url": {"S": company_info.get('companyLogo', '')},
                    "positions": LinkedInProfileMapper._extract_positions_list(positions_list)
                }
            }
            experience_list.append(experience_item)
        
        return {"L": experience_list}
    
    @staticmethod
    def _extract_positions_list(positions: List[Dict]) -> Dict:
        """Extract individual positions within a company"""
        position_list = []
        
        for position in positions:
            start_date = LinkedInProfileMapper._extract_start_date_from_position(position)
            end_date = LinkedInProfileMapper._extract_end_date_from_position(position)
            duration = LinkedInProfileMapper._calculate_position_duration(position)
            
            position_item = {
                "M": {
                    "title": {"S": position.get('title', '')},
                    "subtitle": {"S": position.get('companyName', '')},
                    "duration": {"S": duration},
                    "duration_short": {"S": LinkedInProfileMapper._get_short_duration(duration)},
                    "description": {"S": position.get('description', '')},
                    "description_html": {"S": position.get('description', '')},
                    "start_date": {"S": start_date},
                    "end_date": {"S": end_date},
                    "meta": {"S": duration}
                }
            }
            position_list.append(position_item)
        
        return {"L": position_list}
    
    @staticmethod
    def _calculate_total_duration_at_company(positions: List[Dict]) -> str:
        """Calculate total duration at a company from all positions"""
        if not positions:
            return ""
        
        # For simplicity, use the duration of the longest single position
        # In a real scenario, you'd want to calculate overlaps and gaps
        durations = [LinkedInProfileMapper._calculate_position_duration(pos) for pos in positions]
        return max(durations, key=len) if durations else ""
    
    @staticmethod
    def _calculate_position_duration(position: Dict) -> str:
        """Calculate duration of a single position"""
        start_end_date = position.get('startEndDate', {})
        start = start_end_date.get('start', {})
        end = start_end_date.get('end', {})
        
        start_month = start.get('month')
        start_year = start.get('year')
        end_month = end.get('month') if end else None
        end_year = end.get('year') if end else None
        
        if not start_year:
            return ""
        
        start_date_str = LinkedInProfileMapper._format_month_year(start_month, start_year)
        
        if end_year:
            end_date_str = LinkedInProfileMapper._format_month_year(end_month, end_year)
            years = end_year - start_year
            return f"{start_date_str} - {end_date_str} {years} years" if years > 0 else f"{start_date_str} - {end_date_str} 1 year"
        else:
            return f"{start_date_str} - Present"
    
    @staticmethod
    def _extract_start_date_from_position(position: Dict) -> str:
        """Extract formatted start date from position"""
        start_end_date = position.get('startEndDate', {})
        start = start_end_date.get('start', {})
        
        return LinkedInProfileMapper._format_month_year(start.get('month'), start.get('year'))
    
    @staticmethod
    def _extract_end_date_from_position(position: Dict) -> str:
        """Extract formatted end date from position"""
        start_end_date = position.get('startEndDate', {})
        end = start_end_date.get('end', {})
        
        if not end or not end.get('year'):
            return "Present"
        
        return LinkedInProfileMapper._format_month_year(end.get('month'), end.get('year'))
    
    @staticmethod
    def _format_month_year(month: int, year: int) -> str:
        """Format month and year into readable string"""
        if not year:
            return ""
        
        if month:
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            month_name = months[int(month) - 1] if 1 <= int(month) <= 12 else str(month)
            return f"{month_name} {year}"
        
        return str(year)
    
    @staticmethod
    def _get_short_duration(duration: str) -> str:
        """Extract short duration from full duration string"""
        # Extract just the years/months part
        if " - " in duration:
            parts = duration.split(" - ")
            if len(parts) >= 2:
                duration_part = parts[1].split()
                if len(duration_part) >= 2:
                    return f"{duration_part[0]} {duration_part[1]}"
        return duration
    
    @staticmethod
    def _extract_education_from_schools(profile: Dict) -> Dict:
        """Extract education information from schools"""
        schools = profile.get('schools', {})
        education_history = schools.get('educationHistory', [])
        
        if not education_history:
            return {"L": []}
        
        education_list = []
        for edu in education_history:
            school_info = edu.get('school', {})
            school_name = school_info.get('schoolName', edu.get('schoolName', ''))
            
            start_end_date = edu.get('startEndDate', {})
            start = start_end_date.get('start', {})
            end = start_end_date.get('end', {})
            
            education_item = {
                "M": {
                    "title": {"S": school_name},
                    "degree": {"S": edu.get('degreeName', '')},
                    "field": {"S": edu.get('fieldOfStudy', '')},
                    "start_year": {"S": str(start.get('year', ''))},
                    "end_year": {"S": str(end.get('year', ''))},
                    "description": {"S": ""},
                    "description_html": {"S": ""},
                    "institute_logo_url": {"S": school_info.get('schoolLogo', '')},
                    "url": {"S": school_info.get('linkedInUrl', '')}
                }
            }
            education_list.append(education_item)
        
        return {"L": education_list}
    
    @staticmethod
    def _extract_primary_education(profile: Dict) -> str:
        """Extract primary education details"""
        schools = profile.get('schools', {})
        education_history = schools.get('educationHistory', [])
        
        if education_history:
            # Get the first/most recent education
            first_edu = education_history[0]
            school_info = first_edu.get('school', {})
            return school_info.get('schoolName', first_edu.get('schoolName', ''))
        
        return ""
    
    @staticmethod
    def _create_empty_profile_structure(email: str, error_msg: str = "") -> Dict:
        """Create empty profile structure with error information"""
        return {
            "id": {"S": email.replace('@', '_at_').replace('.', '_')},
            "url": {"S": ""},
            "linkedin_id": {"S": ""},
            "linkedin_num_id": {"S": ""},
            "input": {"M": {"email": {"S": email}}},
            "input_url": {"S": ""},
            "timestamp": {"S": datetime.now().isoformat()},
            "created_at": {"S": datetime.now().isoformat()},
            "updated_at": {"S": datetime.now().isoformat()},
            "updated_by": {"S": "outlook-login-system"},
            "name": {"S": ""},
            "first_name": {"S": ""},
            "last_name": {"S": ""},
            "position": {"S": ""},
            "about": {"S": ""},
            "location": {"S": ""},
            "city": {"S": ""},
            "country_code": {"S": ""},
            "avatar": {"S": ""},
            "banner_image": {"S": "https://static.licdn.com/aero-v1/sc/h/5q92mjc5c51bjlwaj3rs9aa82"},
            "default_avatar": {"BOOL": True},
            "connections": {"N": "0"},
            "followers": {"N": "0"},
            "current_company": {"M": {"name": {"S": ""}, "title": {"S": ""}, "company_id": {"S": ""}, "link": {"S": ""}}},
            "current_company_name": {"S": ""},
            "current_company_company_id": {"S": ""},
            "experience": {"L": []},
            "education": {"L": []},
            "educations_details": {"S": ""},
            "certifications": {"L": []},
            "courses": {"L": []},
            "languages": {"L": []},
            "patents": {"L": []},
            "publications": {"L": []},
            "projects": {"L": []},
            "organizations": {"L": []},
            "activity": {"L": []},
            "posts": {"L": []},
            "recommendations": {"L": []},
            "recommendations_count": {"N": "0"},
            "honors_and_awards": {"L": []},
            "volunteer_experience": {"L": []},
            "people_also_viewed": {"L": []},
            "similar_profiles": {"L": []},
            "bio_links": {"L": []},
            "memorialized_account": {"BOOL": False},
            "snapshot_id": {"S": str(uuid.uuid4())},
            "snapshotid": {"S": str(uuid.uuid4())},
            "new_snapshot_id": {"S": str(uuid.uuid4())},
            "user_id": {"S": email.replace('@', '_at_').replace('.', '_')},
            "error": {"S": error_msg} if error_msg else {}
        }
